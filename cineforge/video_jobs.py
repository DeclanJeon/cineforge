"""Video cut execution: one job per cut, explicit take adoption, length checked."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .jobs import Job, JobError, require_authorized, video_jobs


def plan_jobs(project: Path) -> tuple[Job, ...]:
    return video_jobs(project)


def _duration(path: Path) -> float:
    import subprocess

    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(path)],
                           check=True, capture_output=True, text=True)
    return float(probe.stdout.strip())


def select_take(project: Path, cut_id: str, path: str, *, note: str = '') -> dict[str, Any]:
    """Adopt a rendered take only when it is long enough; previous takes are kept."""
    scene = json.loads((project / 'ssot/scene.json').read_text(encoding='utf-8'))['data']['cuts']
    cut = next((row for row in scene if row['cut_id'] == cut_id), None)
    if cut is None:
        raise JobError(f'unknown_cut: {cut_id}')
    output = project / path
    if not output.is_file():
        raise JobError('take_missing')
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
                              'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'duration': round(actual, 3), 'note': note})
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8')
    return registry['takes'][-1]


def require_lanes(project: Path) -> tuple[Job, ...]:
    jobs = video_jobs(project)
    require_authorized(project, jobs)
    return jobs
