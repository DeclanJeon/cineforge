from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from . import execution_plan
from .project_skills import LOCK, require_pack

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
    if (project / LOCK).is_file():
        names.append(LOCK)
    if (project / execution_plan.PLAN).is_file():
        names += [execution_plan.PLAN, execution_plan.APPROVAL]
    digest = hashlib.sha256()
    for name in names:
        path = project / name
        digest.update(json.dumps([name, _sha(path) if path.is_file() else None]).encode())
    return digest.hexdigest()


def _job(project: Path, *, job_id: str, kind: str, inputs: list[str], prompt: str,
         target: str, params: dict[str, Any], depends_on: tuple[str, ...] = ()) -> Job:
    pins = tuple((name, _sha(project / name)) for name in inputs)
    plan = execution_plan.read(project)
    lane = plan['lanes'].get(kind) if plan else None
    provider, tool = PROVIDER_OF[kind], TOOL_OF[kind]
    if lane:
        provider = lane['provider']
        tool = {'higgsfield': 'generate_video', 'code-motion': 'render_html_motion'}.get(provider, tool)
        if kind == 'dialogue' and provider != PROVIDER_OF['dialogue']:
            from .sound import voice_lane
            tool = voice_lane(provider)[1]
        params = {**params, 'model': lane['model']}
        if kind == 'video_cut' and provider == 'ludyte' and lane['model'] == 'singularity-full-v2':
            edit_seconds = float(params['duration_s'])
            if edit_seconds < 5:
                prompt = prompt.replace(f'길이 {params["duration_s"]}초.', '원본 길이 5초.')
                prompt += f' 원본 5초 안에 편집용 {edit_seconds:g}초 행동 구간을 확보한다.'
                params = {**params, 'duration_s': 5, 'edit_duration_s': edit_seconds}
    spec = {'job_id': job_id, 'kind': kind, 'provider': provider, 'tool': tool,
            'inputs': pins, 'prompt': prompt, 'params': params, 'depends_on': depends_on}
    key = hashlib.sha256(json.dumps([binding(project), spec], sort_keys=True).encode()).hexdigest()
    return Job(job_id, kind, provider, tool, pins, prompt,
               tuple(sorted((str(k), str(v)) for k, v in params.items())), key, depends_on)


def external_voice(project: Path) -> bool:
    """True only when a separate voice (TTS/reference/dubbing) was explicitly requested."""
    meta = project / 'project.json'
    inputs = json.loads(meta.read_text(encoding='utf-8')).get('inputs', {}) if meta.is_file() else {}
    return bool(inputs.get('external_voice'))


def audio_jobs(project: Path) -> tuple[Job, ...]:
    sound = json.loads((project / 'assets/sound_plan.json').read_text(encoding='utf-8'))['cues']
    jobs = []
    separate = external_voice(project)
    for cue in sound:
        if cue['kind'] == 'DIALOGUE' and (not separate or cue.get('provider') == 'native'):
            continue  # default: the video model speaks the line natively
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
    plan = execution_plan.read(project) or {}
    lane = plan.get('lanes', {}).get('video_cut', {})
    selected = execution_plan.code_motion_cuts(project, lane) if lane.get('provider') == 'code-motion' else None
    if selected is not None and not selected <= {row['cut_id'] for row in prompts}:
        raise JobError('code_motion_cut_prompt_missing')
    jobs = []
    for row in prompts:
        if selected is not None and row['cut_id'] not in selected:
            continue
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
    import time

    if (plan := execution_plan.read(project)) is not None:
        _check_scope(project, jobs, plan)
        return
    auth = authority(project)
    until = auth.get('execution_until')
    if auth.get('execution') and isinstance(until, (int, float)) and until < time.time():
        raise JobError('execution_expired')
    blocked = sorted({kind for kind in (job.kind for job in jobs) if REQUIRED[kind] and not auth.get(REQUIRED[kind])})
    if blocked:
        raise JobError(f'execution_not_authorized: {", ".join(blocked)}')
    if auth.get('providers'):
        refused = sorted({job.provider for job in jobs if job.provider not in auth['providers']})
        if refused:
            raise JobError(f'provider_not_allowed: {", ".join(refused)}')


def _check_scope(project: Path, jobs: tuple[Job, ...], plan: dict[str, Any]) -> dict[str, Any]:
    try:
        approval = execution_plan.approved(project, plan)
    except ValueError as exc:
        raise JobError(str(exc)) from exc
    counts: dict[str, int] = {}
    video_lane = plan['lanes'].get('video_cut', {})
    selected = (execution_plan.code_motion_cuts(project, video_lane)
                if video_lane.get('provider') == 'code-motion' and any(job.kind == 'video_cut' for job in jobs) else None)
    if selected is not None and {job.job_id for job in jobs if job.kind == 'video_cut'} != {f'video:{cut}' for cut in selected}:
        raise JobError('execution_scope_changed: code-motion cuts')
    for job in jobs:
        lane = plan['lanes'].get(job.kind)
        counts[job.kind] = counts.get(job.kind, 0) + 1
        if (not lane or job.provider != lane['provider'] or dict(job.params).get('model') != lane['model']
                or counts[job.kind] > lane['max_jobs']):
            raise JobError(f'execution_scope_changed: {job.kind}')
    return approval


def _check_quotes(plan: dict[str, Any], jobs: tuple[Job, ...], quotes: dict[str, Any]) -> None:
    if not isinstance(quotes, dict):
        raise JobError('invalid_execution_quotes')
    if len({job.job_id for job in jobs}) != len(jobs) or set(quotes) - {job.job_id for job in jobs}:
        raise JobError('invalid_execution_quotes')
    totals: dict[str, Any] = {}
    for job in jobs:
        lane = plan['lanes'][job.kind]
        if 'ceiling' not in lane:
            if job.job_id in quotes:
                raise JobError(f'execution_scope_changed: unexpected paid quote for {job.job_id}')
            continue
        quote = quotes.get(job.job_id)
        if (not isinstance(quote, dict) or quote.get('unit') != lane['unit']
                or not isinstance(quote.get('evidence'), str) or not quote['evidence'].strip()):
            raise JobError(f'execution_quote_required: {job.job_id}')
        totals[job.kind] = totals.get(job.kind, 0) + execution_plan.amount(quote.get('amount'))
        if totals[job.kind] > execution_plan.amount(lane['ceiling']):
            raise JobError(f'execution_ceiling_exceeded: {job.kind}')


def write_envelope(project: Path, stage: str, jobs: tuple[Job, ...], *, note: str = '',
                   quotes: dict[str, Any] | None = None) -> Path:
    pack = require_pack(project)
    require_authorized(project, jobs)
    plan = execution_plan.read(project)
    scope = {key: authority(project).get(key) for key in ('execution', 'spend_ceiling', 'providers')}
    if plan is not None:
        if (stage not in ('S08_audio', 'S08_video')
                or any((job.kind == 'video_cut') != (stage == 'S08_video') for job in jobs)):
            raise JobError('execution_scope_changed: wrong stage')
        approval = execution_plan.approved(project, plan)
        _check_quotes(plan, jobs, {} if quotes is None else quotes)
        scope = {'execution_plan_hash': approval['plan_hash'], 'expires_at': approval['expires_at'],
                 'lanes': plan['lanes'], 'quotes': quotes or {}}
    if stage == 'S08_video':
        from dataclasses import asdict
        from .phase_review import review
        review(project, 'prompt', [asdict(job) for job in jobs])
    payload = {'schema_version': 1, 'stage': stage, 'binding': binding(project),
               'project_root': str(project.resolve()), 'note': note,
               'authority': scope,
               'jobs': [{'job_id': job.job_id, 'kind': job.kind, 'provider': job.provider, 'tool': job.tool,
                         'inputs': dict(job.inputs), 'prompt': job.prompt, 'params': dict(job.params),
                         'idempotency_key': job.idempotency_key, 'depends_on': list(job.depends_on)} for job in jobs]}
    if pack is not None:
        payload['skill_pack'] = pack.binding.identity()
    path = project / 'jobs' / f'{stage}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    if plan is not None:
        try:
            with path.open('x', encoding='utf-8') as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
        except FileExistsError:
            if json.loads(path.read_text(encoding='utf-8')) != payload:
                raise JobError('execution_envelope_already_issued')
        return path
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
    pack = require_pack(project)
    envelope = load_envelope(project, stage)
    known = {job['job_id']: job for job in envelope['jobs']}
    path = project / 'receipts' / f'{stage}.json'
    receipt = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {
        'schema_version': 1, 'stage': stage, 'binding': envelope['binding'], 'results': {}}
    if pack is not None:
        receipt['skill_pack'] = pack.binding.identity()
    if receipt['binding'] != envelope['binding']:
        raise JobError('receipt_binding_mismatch')
    for item in results:
        job_id = item.get('job_id')
        status = item.get('status')
        if job_id not in known or status not in ('accepted', 'rejected', 'uncertain'):
            raise JobError(f'invalid_result: {job_id}')
        previous = receipt['results'].get(job_id)
        if status == 'accepted':
            relative = Path(str(item.get('path') or ''))
            output = project / relative
            is_code_motion = known[job_id]['provider'] == 'code-motion'
            if is_code_motion and (relative.is_absolute() or '..' in relative.parts
                                   or not output.resolve().is_relative_to(project.resolve())):
                raise JobError(f'code_motion_output_path: {job_id}')
            if not output.is_file():
                raise JobError(f'output_missing: {job_id}')
            digest = _sha(output)
            if previous and previous['status'] == 'accepted':
                if previous.get('sha256') != digest or (is_code_motion and previous.get('path') != str(relative)):
                    raise JobError(f'receipt_conflict: {job_id}')
                continue
            if previous:
                raise JobError(f'receipt_conflict: {job_id}')
            if is_code_motion:
                from .video_jobs import check_code_motion_output
                check_code_motion_output(output, known[job_id]['params'])
                if _sha(output) != digest:
                    raise JobError(f'code_motion_output_changed: {job_id}')
            receipt['results'][job_id] = {'status': 'accepted', 'path': str(output.relative_to(project)),
                                          'sha256': digest, 'provider_meta': item.get('provider_meta', runner_meta)}
        else:
            if previous and previous['status'] == 'accepted':
                raise JobError(f'receipt_conflict: {job_id}')
            receipt['results'][job_id] = {'status': status, 'error': item.get('error', '')}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    return path
