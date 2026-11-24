"""Validate and record the operator-approved scope before paid production."""
from __future__ import annotations

import hashlib
import json
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PLAN = 'execution-plan.json'
APPROVAL = 'execution-plan-approval.json'


def amount(value: Any) -> Decimal:
    try:
        if type(value) not in (str, int):
            raise ValueError
        result = Decimal(value)
        if not result.is_finite() or result < 0 or result > 10**12 or result.as_tuple().exponent < -6:
            raise ValueError
        return result
    except (ValueError, InvalidOperation) as exc:
        raise ValueError('invalid_execution_amount') from exc


def digest(plan: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read(root: Path) -> dict[str, Any] | None:
    path = root / PLAN
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def code_motion_cuts(project: Path, lane: dict[str, Any]) -> set[str]:
    scene = json.loads((project / 'ssot/scene.json').read_text(encoding='utf-8'))
    known = {row['cut_id'] for row in scene['data']['cuts']}
    if 'cut_ids' in lane:
        cuts = lane['cut_ids']
        if (not isinstance(cuts, list) or not cuts or any(not isinstance(cut, str) or cut not in known for cut in cuts)
                or len(set(cuts)) != len(cuts)):
            raise ValueError('invalid_code_motion_cut_ids')
        selected = set(cuts)
    else:
        selected = known
    plan = json.loads((project / 'plan.json').read_text(encoding='utf-8'))
    brief = plan['production_spec'].get('motion_brief')
    if brief and selected != {row['cut'] for row in brief['route_by_cut'] if row['route'] == 'code'}:
        raise ValueError('code_motion_cut_scope_mismatch')
    return selected


def proposal(project: Any, data: Any) -> dict[str, Any]:
    from .jobs import PROVIDER_OF

    if not isinstance(data, dict) or set(data) != {'lanes'} or not isinstance(data['lanes'], list) or not data['lanes']:
        raise ValueError('execution_plan_requires_lanes')
    lanes: dict[str, dict[str, Any]] = {}
    for row in data['lanes']:
        if not isinstance(row, dict):
            raise ValueError('invalid_execution_lane')
        kind, provider, model, count = (row.get(key) for key in ('kind', 'provider', 'model', 'max_jobs'))
        if (not isinstance(kind, str) or kind == 'image' or kind not in PROVIDER_OF or kind in lanes
                or (provider != PROVIDER_OF[kind] and (kind, provider) not in (('video_cut', 'higgsfield'), ('video_cut', 'code-motion'), ('dialogue', 'typecast')))
                or not isinstance(model, str) or not model.strip() or type(count) is not int or count <= 0):
            raise ValueError('invalid_execution_lane')
        fields = {'kind', 'provider', 'model', 'max_jobs'}
        if (kind, provider) not in (('video_cut', 'ludyte'), ('video_cut', 'code-motion')):
            fields |= {'unit', 'estimate', 'ceiling'}
            if not isinstance(row.get('unit'), str) or not row['unit'].strip() or not 0 < amount(row.get('ceiling')):
                raise ValueError('execution_ceiling_required')
            if row.get('estimate') is not None and amount(row['estimate']) > amount(row['ceiling']):
                raise ValueError('execution_ceiling_exceeded')
        if provider == 'code-motion' and 'cut_ids' in row:
            fields.add('cut_ids')
        if set(row) != fields:
            raise ValueError('invalid_execution_lane_fields')
        if provider == 'code-motion':
            if model != 'html-seek-v1':
                raise ValueError('invalid_code_motion_model')
            code_motion_cuts(project.root, row)
        lanes[kind] = row
    plan = {'schema_version': 1, 'project_id': project.read('project.json')['project_id'], 'lanes': lanes}
    if plan != read(project.root):
        if any((project.root / 'jobs').glob('S08_*.json')):
            raise ValueError('execution_envelope_already_issued: reconcile existing jobs before revising scope')
        project.write(PLAN, plan)
    return {'plan_hash': digest(plan), **plan}


def approve(project: Any, plan_hash: str, hours: int) -> dict[str, Any]:
    plan = read(project.root)
    if plan is None or digest(plan) != plan_hash:
        raise ValueError('execution_plan_hash_mismatch')
    if hours <= 0:
        raise ValueError('execution_hours_must_be_positive')
    existing = project.read(APPROVAL)
    if existing and existing['plan_hash'] == plan_hash and existing['expires_at'] > time.time():
        return existing
    if any((project.root / 'jobs').glob('S08_*.json')):
        raise ValueError('execution_envelope_already_issued: reconcile existing jobs before reauthorizing')
    approval = {'plan_hash': plan_hash, 'expires_at': int(time.time()) + hours * 3600,
                'source': 'operator_approval_recorded_by_caller'}
    project.write(APPROVAL, approval)
    project.log('execution_plan_approved', **approval)
    return approval


def approved(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    path = root / APPROVAL
    approval = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    if approval.get('plan_hash') != digest(plan):
        raise ValueError('execution_plan_not_approved')
    expiry = approval.get('expires_at')
    if type(expiry) is not int or expiry <= time.time():
        raise ValueError('execution_expired')
    return approval
