from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

JOB_KINDS = ('image', 'video_cut', 'ost', 'bgm', 'sfx', 'dialogue')
PROVIDER_OF = {'ost': 'suno', 'bgm': 'suno', 'sfx': 'elevenlabs', 'dialogue': 'fish_audio',
               'video_cut': 'ludyte', 'image': 'codex-imagen'}
TOOL_OF = {'ost': 'suno_generate', 'bgm': 'suno_generate', 'sfx': 'elevenlabs_sound_effect',
           'dialogue': 'fish_audio_tts', 'video_cut': 'send_message', 'image': 'image_generation'}
REQUIRED = {'ost': 'execution', 'bgm': 'execution', 'sfx': 'execution', 'dialogue': 'execution',
            'video_cut': 'execution', 'image': None}


class JobError(ValueError):
    """A job set is not buildable or a result cannot be recorded."""


@dataclass(frozen=True, slots=True)
class Job:
    job_id: str
    kind: str
    provider: str
    tool: str
    inputs: tuple[tuple[str, str], ...]
    prompt: str
    params: tuple[tuple[str, str], ...] = ()
    idempotency_key: str = ''
    depends_on: tuple[str, ...] = ()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(project: Path) -> str:
    """Everything a result depends on, without timestamps."""
    names = ['project.json', 'authority.json', 'plan.json', 'selection.json',
             'ssot/scene.json', 'ssot/audio.json', 'ssot/camera.json', 'ssot/motion.json',
             'assets/sound_plan.json', 'assets/video_prompts.json', 'assets/asset_registry.json']
    digest = hashlib.sha256()
    for name in names:
        path = project / name
        digest.update(json.dumps([name, _sha(path) if path.is_file() else None]).encode())
    return digest.hexdigest()


def _job(project: Path, *, job_id: str, kind: str, inputs: list[str], prompt: str,
         target: str, params: dict[str, Any], depends_on: tuple[str, ...] = ()) -> Job:
    pins = tuple((name, _sha(project / name)) for name in inputs)
    spec = {'job_id': job_id, 'kind': kind, 'provider': PROVIDER_OF[kind], 'tool': TOOL_OF[kind],
            'inputs': pins, 'prompt': prompt, 'params': params, 'depends_on': depends_on}
    key = hashlib.sha256(json.dumps([binding(project), spec], sort_keys=True).encode()).hexdigest()
    return Job(job_id, kind, PROVIDER_OF[kind], TOOL_OF[kind], pins, prompt,
               tuple(sorted((str(k), str(v)) for k, v in params.items())), key, depends_on)


def audio_jobs(project: Path) -> tuple[Job, ...]:
    sound = json.loads((project / 'assets/sound_plan.json').read_text(encoding='utf-8'))['cues']
    jobs = []
    for cue in sound:
        kind = {'OST': 'ost', 'BGM': 'bgm', 'SFX': 'sfx', 'AMBIENCE': 'sfx', 'DIALOGUE': 'dialogue'}.get(cue['kind'])
        if kind is None:
            raise JobError(f'unsupported cue: {cue["kind"]}')
        jobs.append(_job(project, job_id=f'audio:{cue["cue_id"]}:{kind}', kind=kind, inputs=[],
                         prompt=cue['prompt'], target=cue['cue_id'],
                         params={'tc_in': cue['tc_in'], 'tc_out': cue['tc_out'], 'vocal': cue['vocal'],
                                 'loop': cue['loop'], 'role': cue['role']}))
    return tuple(jobs)


def video_jobs(project: Path) -> tuple[Job, ...]:
    prompts = json.loads((project / 'assets/video_prompts.json').read_text(encoding='utf-8'))['prompts']
    assets = {row['asset_id']: row for row in json.loads((project / 'assets/asset_registry.json').read_text(encoding='utf-8'))['assets']}
    outputs_path = project / 'assets/image_outputs.json'
    outputs = json.loads(outputs_path.read_text(encoding='utf-8')) if outputs_path.is_file() else {}
    jobs = []
    for row in prompts:
        paths, missing = [], []
        for ref in row['refs']:
            candidate = outputs.get(ref) or (assets[ref]['path'] if ref in assets else None)
            ready = (ref in outputs) or (ref in assets and assets[ref].get('status') in ('available', 'verified'))
            if not candidate or not ready or not (project / candidate).is_file():
                missing.append(ref)
            else:
                paths.append(candidate)
        if missing:
            raise JobError(f'image_reference_not_ready: {", ".join(missing)}')
        jobs.append(_job(project, job_id=f'video:{row["cut_id"]}', kind='video_cut',
                         inputs=paths, prompt=row['prompt'], target=row['cut_id'],
                         params={'duration_s': row['params']['duration_s'], 'aspect': row['params']['aspect'],
                                 'audio': row['params']['audio']},
                         depends_on=tuple(row['refs'])))
    return tuple(jobs)


def authority(project: Path) -> dict[str, Any]:
    return json.loads((project / 'authority.json').read_text(encoding='utf-8'))


def require_authorized(project: Path, jobs: tuple[Job, ...], *, spend_ceiling: str | None = None) -> None:
    auth = authority(project)
    blocked = sorted({kind for kind in (job.kind for job in jobs) if REQUIRED[kind] and not auth.get(REQUIRED[kind])})
    if blocked:
        raise JobError(f'execution_not_authorized: {", ".join(blocked)}')
    if auth.get('providers'):
        refused = sorted({job.provider for job in jobs if job.provider not in auth['providers']})
        if refused:
            raise JobError(f'provider_not_allowed: {", ".join(refused)}')


def write_envelope(project: Path, stage: str, jobs: tuple[Job, ...], *, note: str = '') -> Path:
    require_authorized(project, jobs)
    payload = {'schema_version': 1, 'stage': stage, 'binding': binding(project),
               'project_root': str(project.resolve()), 'note': note,
               'authority': {key: authority(project).get(key) for key in ('execution', 'spend_ceiling', 'providers')},
               'jobs': [{'job_id': job.job_id, 'kind': job.kind, 'provider': job.provider, 'tool': job.tool,
                         'inputs': dict(job.inputs), 'prompt': job.prompt, 'params': dict(job.params),
                         'idempotency_key': job.idempotency_key, 'depends_on': list(job.depends_on)} for job in jobs]}
    path = project / 'jobs' / f'{stage}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def load_envelope(project: Path, stage: str) -> dict[str, Any]:
    path = project / 'jobs' / f'{stage}.json'
    if not path.is_file():
        raise JobError('envelope_missing')
    envelope = json.loads(path.read_text(encoding='utf-8'))
    if envelope.get('binding') != binding(project):
        raise JobError('envelope_stale')
    return envelope


def record_results(project: Path, stage: str, results: list[dict[str, Any]], *, runner_meta: str = '') -> Path:
    envelope = load_envelope(project, stage)
    known = {job['job_id']: job for job in envelope['jobs']}
    path = project / 'receipts' / f'{stage}.json'
    receipt = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {
        'schema_version': 1, 'stage': stage, 'binding': envelope['binding'], 'results': {}}
    if receipt['binding'] != envelope['binding']:
        raise JobError('receipt_binding_mismatch')
    for item in results:
        job_id = item.get('job_id')
        status = item.get('status')
        if job_id not in known or status not in ('accepted', 'rejected', 'uncertain'):
            raise JobError(f'invalid_result: {job_id}')
        previous = receipt['results'].get(job_id)
        if status == 'accepted':
            output = project / str(item.get('path') or '')
            if not output.is_file():
                raise JobError(f'output_missing: {job_id}')
            digest = _sha(output)
            if previous and previous['status'] == 'accepted':
                if previous.get('sha256') != digest:
                    raise JobError(f'receipt_conflict: {job_id}')
                continue
            if previous:
                raise JobError(f'receipt_conflict: {job_id}')
            receipt['results'][job_id] = {'status': 'accepted', 'path': str(output.relative_to(project)),
                                          'sha256': digest, 'provider_meta': item.get('provider_meta', runner_meta)}
        else:
            if previous and previous['status'] == 'accepted':
                raise JobError(f'receipt_conflict: {job_id}')
            receipt['results'][job_id] = {'status': status, 'error': item.get('error', '')}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    return path
