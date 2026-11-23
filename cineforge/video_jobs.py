"""Video cut execution: one job per cut, explicit take adoption, length checked."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from . import execution_plan
from .jobs import Job, JobError, require_authorized, video_jobs


def plan_jobs(project: Path) -> tuple[Job, ...]:
    return video_jobs(project)


def check_code_motion_output(path: Path, params: dict[str, str]) -> None:
    try:
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(path)],
                               check=True, capture_output=True, text=True, timeout=30)
        videos = [row for row in json.loads(probe.stdout)['streams'] if row['codec_type'] == 'video'
                  and not row.get('disposition', {}).get('attached_pic')]
        if len(videos) != 1:
            raise ValueError('expected one video stream')
        video = videos[0]
        sar = video.get('sample_aspect_ratio', '1:1')
        aspect = Fraction(video['width'], video['height']) * (Fraction(1) if sar == 'N/A' else Fraction(sar.replace(':', '/')))
        if any(int(side.get('rotation', 0)) % 180 for side in video.get('side_data_list', [])):
            aspect = 1 / aspect
        if aspect != Fraction(params['aspect'].split()[0].replace(':', '/')):
            raise ValueError(f'aspect: {aspect} != {params["aspect"]}')
        fps = Fraction(video['avg_frame_rate'])
        duration = Fraction(video['duration'])
        expected = Fraction(params['duration_s'])
        if fps <= 0 or expected <= 0 or abs(duration - expected) > min(Fraction(1, 20), 1 / fps):
            raise ValueError(f'duration: {duration} != {expected}')
        for key, actual in [('width', video['width']), ('height', video['height']), ('fps', fps)]:
            if key in params and Fraction(params[key]) != actual:
                raise ValueError(f'{key}: {actual} != {params[key]}')
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, ZeroDivisionError) as exc:
        raise JobError(f'invalid_code_motion_output: {exc}') from exc


def check_code_motion_take(project: Path, cut_id: str, output: Path, digest: str) -> None:
    plan = execution_plan.read(project) or {}
    lane = plan.get('lanes', {}).get('video_cut', {})
    if lane.get('provider') != 'code-motion':
        return
    receipt_path = project / 'receipts/S08_video.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.is_file() else {}
    results = receipt.get('results', {})
    job_id = f'video:{cut_id}'
    resolved = output.resolve()
    if cut_id not in execution_plan.code_motion_cuts(project, lane):
        if any(row['status'] == 'accepted' and ((project / row['path']).resolve() == resolved or row['sha256'] == digest)
               for row in results.values()):
            raise JobError(f'code_motion_take_wrong_cut: {cut_id}')
        return
    row = results.get(job_id, {})
    if (row.get('status') != 'accepted' or not resolved.is_relative_to(project.resolve())
            or row.get('path') != str(output.relative_to(project)) or row.get('sha256') != digest):
        raise JobError(f'code_motion_take_not_accepted: {cut_id}')
    envelope_path = project / 'jobs/S08_video.json'
    envelope = json.loads(envelope_path.read_text(encoding='utf-8')) if envelope_path.is_file() else {}
    job = next((job for job in envelope.get('jobs', []) if job['job_id'] == job_id), {})
    # Verification can update the asset registry after receipt; compare immutable scope
    # and cut requirements instead of reapplying the pre-execution binding.
    prompts = json.loads((project / 'assets/video_prompts.json').read_text(encoding='utf-8'))['prompts']
    prompt = next((row for row in prompts if row['cut_id'] == cut_id), {})
    if (receipt.get('binding') != envelope.get('binding') or job.get('provider') != 'code-motion'
            or envelope.get('authority', {}).get('execution_plan_hash') != execution_plan.digest(plan)
            or any(job['params'].get(key) != str(prompt.get('params', {}).get(key)) for key in ('duration_s', 'aspect'))):
        raise JobError(f'code_motion_take_stale: {cut_id}')


def _duration(path: Path) -> float:
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(path)],
                           check=True, capture_output=True, text=True)
    return float(probe.stdout.strip())


def select_take(project: Path, cut_id: str, path: str, *, note: str = '') -> dict[str, Any]:
    """Adopt a rendered take only when it is long enough; previous takes are kept."""
    scene = json.loads((project / 'ssot/scene.json').read_text(encoding='utf-8'))['data']['cuts']
    cut = next((row for row in scene if row['cut_id'] == cut_id), None)
    if cut is None:
        raise JobError(f'unknown_cut: {cut_id}')
    relative = Path(path)
    output = project / relative
    if relative.is_absolute() or '..' in relative.parts or not output.resolve().is_relative_to(project.resolve()):
        raise JobError('take_path_outside_project')
    if not output.is_file():
        raise JobError('take_missing')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    check_code_motion_take(project, cut_id, output, digest)
    actual = _duration(output)
    if actual + 0.05 < float(cut['duration']):
        raise JobError(f'take_too_short: {actual:.2f}s < {cut["duration"]}s')
    registry_path = project / 'takes/take_registry.json'
    registry = json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.is_file() else {'schema_version': 1, 'takes': []}
    for row in registry['takes']:
        if row.get('cut_id') == cut_id:
            row['status'] = 'superseded'
    take_id = f'{cut_id}:T{sum(1 for row in registry["takes"] if row.get("cut_id") == cut_id) + 1}'
    registry['takes'].append({'take_id': take_id, 'cut_id': cut_id, 'status': 'available', 'path': str(output.relative_to(project)),
                              'sha256': digest, 'duration': round(actual, 3), 'note': note})
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8')
    return registry['takes'][-1]


def require_lanes(project: Path) -> tuple[Job, ...]:
    jobs = video_jobs(project)
    require_authorized(project, jobs)
    return jobs
