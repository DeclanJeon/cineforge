"""Delivery bundle: only a gated, fully inspected film reaches `final/`."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from .edit_plan import build as build_plan
from .final_qa import inspect
from .gate import check as gate_check
from .skills import pins as skill_pins
from .subtitles import to_srt


class DeliveryError(RuntimeError):
    """Delivery is blocked; the previous bundle is preserved."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deliver(project: Path, *, video: Path | None = None, burn: bool = False) -> dict[str, Any]:
    plan = build_plan(project)
    plan_path = project / 'edit/edit_plan.json'
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    srt = project / 'edit/subtitles.srt'
    if plan['subtitles']:
        to_srt(plan['subtitles'], srt, runtime=float(plan['runtime']))
    source = video or project / 'edit/render.mp4'
    if not source.is_file():
        raise DeliveryError('render_missing')
    report = inspect(project, source, plan=plan)
    if report['status'] != 'pass':
        failed = [row['id'] for row in report['checks'] if not row['ok']]
        raise DeliveryError(f'final_qa_failed: {", ".join(failed)}')
    gate = gate_check(project)
    if gate.status != 'pass':
        raise DeliveryError(f'gate_blocked: {len(gate.blockers)}')
    target = project / 'final' / f'{project.name}.mp4'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    shutil.copyfile(source, temporary)
    temporary.replace(target)
    final_srt = project / 'final' / f'{project.name}.srt'
    if srt.is_file():
        shutil.copyfile(srt, final_srt)
    bundle = {'schema_version': 1, 'project_id': project.name, 'video': str(target.relative_to(project)),
              'sha256': _sha(target), 'duration': float(plan['runtime']),
              'width': int(plan['width']), 'height': int(plan['height']), 'fps': int(plan['fps']),
              'subtitles': str(final_srt.relative_to(project)) if final_srt.is_file() else None,
              'burned_in': burn, 'gate': gate.as_dict(), 'final_qa': report['status'],
              'ai_disclosure': True, 'skills': skill_pins()}
    delivery = project / 'final/delivery.json'
    delivery.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
    return bundle
