"""Deterministic edit plan from SSOT, adopted takes, audio registry and dialogue."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import execution_plan
from .video_jobs import check_code_motion_take


class EditError(ValueError):
    """The plan cannot be assembled as specified."""


ASPECT = {'9:16': (1080, 1920), '16:9': (1920, 1080), '1:1': (1080, 1080), '4:5': (1080, 1350)}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def build(project: Path) -> dict[str, Any]:
    scene = _read(project / 'ssot/scene.json')['data']['cuts']
    takes = (_read(project / 'takes/take_registry.json') or {'takes': []})['takes']
    adopted = {row['cut_id']: row for row in takes if row['status'] in ('available', 'verified')}
    audio = (_read(project / 'audio/audio_registry.json') or {'cues': []})['cues']
    sound = (_read(project / 'assets/sound_plan.json') or {'cues': []})['cues']
    by_cue = {row['cue_id']: row for row in sound}
    selection = _read(project / 'selection.json') or {}
    aspect = '9:16'
    runtime = max((float(cut['end']) for cut in scene), default=0.0)
    scope = execution_plan.read(project) or {}
    code_motion = scope.get('lanes', {}).get('video_cut', {}).get('provider') == 'code-motion'
    cuts = []
    for cut in scene:
        take = adopted.get(cut['cut_id'])
        if take is None:
            raise EditError(f'missing_take: {cut["cut_id"]}')
        if code_motion:
            output = project / take['path']
            if not output.is_file():
                raise EditError(f'file_missing: {cut["cut_id"]}')
            check_code_motion_take(project, cut['cut_id'], output, hashlib.sha256(output.read_bytes()).hexdigest())
        if float(take['duration']) + 0.05 < float(cut['duration']):
            raise EditError(f'take_too_short: {cut["cut_id"]}')
        cuts.append({'cut_id': cut['cut_id'], 'take_id': take['take_id'], 'path': take['path'],
                     'in': 0.0, 'out': round(float(cut['duration']), 3), 'transition': 'cut'})
    timeline = []
    for row in audio:
        if row.get('status') not in ('available', 'verified'):
            continue
        cue = by_cue.get(row['cue_id'])
        if cue is None:
            continue
        timeline.append({'cue_id': row['cue_id'], 'kind': row.get('kind', cue['kind']), 'path': row['path'],
                         'in': float(cue['tc_in']), 'out': float(cue['tc_out']),
                         'gain_db': {'DIALOGUE': 0.0, 'SFX': -6.0, 'BGM': -12.0, 'OST': -8.0, 'AMBIENCE': -18.0}.get(cue['kind'], -12.0)})
    subtitles = [{'in': float(cut['start']), 'out': float(cut['end']), 'text': str(cut['dialogue']), 'cut_id': cut['cut_id']}
                 for cut in scene if cut.get('dialogue')]
    width, height = ASPECT[aspect]
    proxy_path = project / 'edit/proxy.json'
    proxy = _read(proxy_path) if proxy_path.is_file() else None
    if proxy:
        width, height = int(proxy['width']), int(proxy['height'])
    return {'schema_version': 1, 'runtime': round(runtime, 3), 'fps': 24, 'aspect': aspect,
            'width': width, 'height': height, 'proxy': bool(proxy), 'cuts': cuts,
            'audio': sorted(timeline, key=lambda row: (row['in'], row['cue_id'])), 'subtitles': subtitles,
            'selection_aspect': selection.get('aspect')}


def validate(project: Path, plan: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    runtime = float(plan['runtime'])
    total = round(sum(float(row['out']) - float(row['in']) for row in plan['cuts']), 2)
    if abs(total - runtime) > 0.25:
        issues.append(f'cut_total_mismatch: {total:.2f} != {runtime:.2f}')
    for row in plan['cuts']:
        if not (project / row['path']).is_file():
            issues.append(f'file_missing: {row["cut_id"]}')
    for row in plan['audio']:
        if not (project / row['path']).is_file():
            issues.append(f'audio_missing: {row["cue_id"]}')
        if float(row['in']) < 0 or float(row['out']) > runtime + 0.05:
            issues.append(f'audio_out_of_range: {row["cue_id"]}')
    return issues
