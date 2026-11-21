"""Persistent, project-wide two-pass host review (no media generation)."""
import fcntl
import hashlib
import json
from pathlib import Path

from .providers.base import AgentInputRequired
from .providers.host_agent import _HostIO
from .receipts import atomic_text

PRE = ('script.md', 'plan.json', 'ssot/story.json', 'ssot/scene.json', 'ssot/camera.json',
       'ssot/motion.json', 'ssot/character.json', 'ssot/world.json', 'assets/frames.json',
       'assets/image_prompts.json', 'assets/video_prompts.json', 'assets/sound_plan.json')
RULES = {
    'pre': 'Inspect the files, not just their names. Cross-check all three pairs of script, cut directions and panels. For every cut check must-show/hide, cause and response, persona, expression, action, speed, dialogue, voice, props, location, reused audio and cue timing. Distinguish planned boards from inspected images.',
    'prompt': 'First infer expected start/action/end and ambiguity using ONLY each submitted prompt, params and actual reference images. Then compare to cut intent, persona, sound routing, reveal timing, provider capabilities and usable edit duration. Prediction is not observation.'}


def _fingerprint(root: Path, packets=None) -> tuple[dict[str, str], str]:
    missing = [name for name in PRE if not (root/name).is_file()]
    if missing:
        raise ValueError(f'review inputs not ready: {missing}')
    names = list(PRE)
    extra = 'assets/motion_assets.json'
    if (root/extra).is_file():
        names.append(extra)
    files = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}
    digest = hashlib.sha256(json.dumps([files, packets], sort_keys=True).encode()).hexdigest()
    return files, digest


def reviewed_plan_hash(root: Path) -> str:
    """Read-only check; execution must not create a new review pass."""
    ledger = root/'reviews/pre-passes.json'
    history = json.loads(ledger.read_text()) if ledger.is_file() else []
    files, digest = _fingerprint(root)
    if not history or history[-1]['digest'] != digest or (len(history) == 1 and history[-1]['findings']):
        raise ValueError('local motion inputs do not match the completed preproduction review')
    return files['plan.json']


def review(root: Path, phase: str, packets=None):
    """Host inspects artifacts; mock projects never purport to have semantic QA."""
    if json.loads((root/'project.json').read_text()).get('provider_mode') == 'mock':
        return
    directory = root/'reviews'
    directory.mkdir(exist_ok=True)
    ledger = directory/f'{phase}-passes.json'
    with (directory/f'.{phase}.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        history = json.loads(ledger.read_text()) if ledger.exists() else []
        files, digest = _fingerprint(root, packets)
        if history and (len(history) == 2 or (not history[-1]['findings'] and digest == history[-1]['digest'])):
            if digest != history[-1]['digest']:
                raise ValueError('reviewed version changed: restore last reviewed inputs before proceeding')
            return
        if history and digest == history[-1]['digest']:
            raise ValueError(f'apply consolidated fixes from {ledger} before resuming')
        cuts = [row['cut_id'] for row in json.loads((root/'ssot/scene.json').read_text())['data']['cuts']]
        request = {'required_cut_ids': cuts, 'response_contract': 'Include cut_evidence: object keyed by every required_cut_id; record specific observations, not just a verdict. In pass 2 unchanged cuts may cite pass 1.', 'instructions': RULES[phase] + ' Return {"evidence": nonempty inspection summary, "findings": [consolidated actionable strings naming cut, evidence, fix and acceptance]}. No preference-only edits. Round two: check changed cuts and dependencies only. Never generate media.',
                   'project': str(root.resolve()), 'files': files, 'packets': packets,
                   'digest': digest, 'prior': history}
        try:
            reply = _HostIO(root/'agent_io').exchange(f'review_{phase}_{len(history)+1}_{digest[:16]}', request)
        except AgentInputRequired as exc:
            raise ValueError(f'host review pending: {exc.request_path} → {exc.response_path}') from None
        if not isinstance(reply, dict) or not isinstance(reply.get('evidence'), str) or not reply['evidence'].strip() or not isinstance(reply.get('findings'), list) or not all(isinstance(s,str) and s.strip() for s in reply['findings']):
            raise ValueError('invalid phase review response')
        observations = reply.get('cut_evidence')
        if not isinstance(observations, dict) or set(observations) != set(cuts) or not all(isinstance(v, str) and v.strip() for v in observations.values()):
            raise ValueError('missing per-cut review evidence')
        history.append({'digest': digest, 'evidence': reply['evidence'], 'cut_evidence': observations, 'findings': reply['findings']})
        atomic_text(ledger, json.dumps(history, ensure_ascii=False, indent=2))
        if len(history) == 1 and reply['findings']:
            raise ValueError(f'apply consolidated fixes from {ledger} before resuming')
