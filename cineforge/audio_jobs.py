"""Audio execution lanes: cue jobs in, verified-ready registry out."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .jobs import Job, JobError, audio_jobs, require_authorized

PROVIDER_DIR = {'suno': 'audio/music', 'elevenlabs': 'audio/sfx', 'fish_audio': 'audio/voice', 'typecast': 'audio/voice'}


def plan_jobs(project: Path) -> tuple[Job, ...]:
    return audio_jobs(project)


def apply_results(project: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Register accepted cue files; a failed cue stays failed and never blocks siblings."""
    jobs = {job.job_id: job for job in audio_jobs(project)}
    path = project / 'audio/audio_registry.json'
    registry = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'schema_version': 1, 'cues': []}
    known = {row['cue_id']: row for row in registry['cues']}
    for item in results:
        job = jobs.get(str(item.get('job_id')))
        if job is None:
            raise JobError(f'unknown_job: {item.get("job_id")}')
        cue_id = job.job_id.split(':')[1]
        if item.get('status') != 'accepted':
            known[cue_id] = {'cue_id': cue_id, 'status': item.get('status', 'failed'), 'error': item.get('error', '')}
            continue
        output = project / str(item.get('path') or '')
        if not output.is_file():
            raise JobError(f'output_missing: {cue_id}')
        known[cue_id] = {'cue_id': cue_id, 'status': 'available', 'path': str(output.relative_to(project)),
                         'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'provider': job.provider,
                         'kind': job.kind, 'version': int(known.get(cue_id, {}).get('version', 0)) + 1}
    registry['cues'] = [known[key] for key in sorted(known)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8')
    return registry


def require_lanes(project: Path) -> tuple[Job, ...]:
    jobs = audio_jobs(project)
    require_authorized(project, jobs)
    return jobs
