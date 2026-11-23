"""Goal driver: evaluate evidence, pick ONE permitted next action, stop at a justified state."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import goal_attempts as attempts, goal_contract as contract
from .goal_evidence import evaluate, sha256

MAX_ACTIONS = 32
CEILING = {'text_storyboard': 'S06_storyboard'}
BOARD_FORBIDDEN = {'execute', 'results', 'motion', 'edit', 'render', 'deliver', 'complete', 'select-take', 'qa-final', 'qa-playback'}
EXIT = {'satisfied': 0, 'needs_user': 3, 'waiting_external': 3, 'busy': 3, 'needs_reconciliation': 4, 'blocked': 4}


def ceiling(root: Path) -> str | None:
    goal = contract.read(root)
    return CEILING.get(goal['kind']) if goal else None


def ensure_allowed(root: Path, command: str) -> None:
    """Manual CLI commands may not step outside the goal. Projects without a goal are untouched."""
    goal = contract.read(Path(root))
    if goal is None:
        return
    if goal['kind'] == 'text_storyboard' and command in BOARD_FORBIDDEN:
        raise contract.GoalError(f'goal text_storyboard forbids `{command}`')
    if goal['kind'] == 'delivery_mp4' and command == 'deliver':
        render = Path(root) / 'edit/render.mp4'
        review = json.loads((Path(root) / 'reviews/user_review.json').read_text()) if (Path(root) / 'reviews/user_review.json').is_file() else {}
        if not render.is_file() or review.get('render_sha256') != sha256(render):
            raise contract.GoalError('goal delivery_mp4: user approval for this exact render is required (`cineforge accept <project> final`)')


def _result(state: str, goal: dict[str, Any], assessment: dict[str, Any], *, next_action: str | None = None,
            reason: str | None = None, **extra: Any) -> dict[str, Any]:
    return {'state': state, 'goal_revision': goal['revision'], 'unmet': assessment['unmet'], 'next_action': next_action,
            'evidence': assessment['evidence'], 'reason': reason, **extra}


def _stage_state(project: Any, goal: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any] | None:
    prog = project.progress()
    sid = prog['current_stage']
    st = prog['stages'].get(sid) if sid else None
    if not st:
        return None
    note, status = st.get('note') or '', st['status']
    pid = Path(project.root)
    if status == 'waiting_user':
        return _result('needs_user', goal, assessment, next_action=note or f'cineforge accept {pid} plan', reason=sid)
    if status in ('waiting_agent', 'waiting_external'):
        return _result('waiting_external', goal, assessment, next_action=note, reason=sid)
    if status in ('blocked', 'failed', 'stale'):
        kind = 'needs_user' if ('권한' in note or '승인' in note or '--image-limit' in note or 'grant' in note) else 'blocked'
        return _result(kind, goal, assessment, next_action=note, reason=f'{sid}:{status}')
    return None


def _fix_duration(project: Any, goal: dict[str, Any]) -> bool:
    """Rescale plan cut durations to the target frame count. Refuses when anything is locked or downstream exists."""
    want, fps = goal['constraints'].get('duration_s'), 24
    prog, plan = project.progress(), project.read('plan.json')
    if want is None or plan is None or project.read('ssot/scene.json').get('locked'):
        return False
    if prog['stages']['S07_assets']['status'] != 'pending' or any(c.get('locked') for s in plan['scenes'] for c in s['cuts']):
        return False
    cuts = [c for s in plan['scenes'] for c in s['cuts']]
    total = round(float(want) * fps)
    if total < len(cuts):
        return False
    current = sum(float(c['duration']) for c in cuts)
    raw = [float(c['duration']) / current * total for c in cuts]
    frames = [max(1, int(r)) for r in raw]
    order = sorted(range(len(cuts)), key=lambda i: (-(raw[i] - int(raw[i])), i))
    k = 0
    while sum(frames) < total:
        frames[order[k % len(order)]] += 1
        k += 1
    while sum(frames) > total:
        i = max((i for i in range(len(frames)) if frames[i] > 1), key=lambda i: (frames[i], -i))
        frames[i] -= 1
    t, n = 0.0, 0
    for s in plan['scenes']:
        s['start'] = round(t, 4)
        for c in s['cuts']:
            c['duration'] = round(frames[n] / fps, 4)
            t += frames[n] / fps
            n += 1
        s['end'] = round(t, 4)
    plan.setdefault('meta', {})['runtime_s'] = float(want)
    project.write('plan.json', plan)
    project.reset_from('S06_storyboard')
    project.log('goal_fix_duration', frames=frames)
    return True


def _post_production(project: Any, goal: dict[str, Any], assessment: dict[str, Any], seen: set[str]) -> dict[str, Any] | None:
    """MP4 goal after G2: decide from evidence, not stage status. Returns a terminal result or None after one action."""
    from . import assembly, edit_plan, final_qa, gate
    from .delivery import DeliveryError, deliver

    root = Path(project.root)
    scene = project.read('ssot/scene.json')['data']['cuts']
    takes = {r['cut_id'] for r in (project.read('takes/take_registry.json') or {'takes': []})['takes'] if r['status'] in ('available', 'verified')}
    pid = root.name
    if any(c['cut_id'] not in takes for c in scene):
        return _external(project, goal, assessment, 'S08_generation')
    render = root / 'edit/render.mp4'
    marker = root / 'goal/render_inputs.json'
    wanted = _render_inputs(root)
    stale = not render.is_file() or not marker.is_file() or json.loads(marker.read_text()).get('inputs') != wanted
    if stale:
        plan = edit_plan.build(root)
        issues = edit_plan.validate(root, plan)
        if issues:
            return _result('blocked', goal, assessment, reason='edit_plan_invalid', next_action='; '.join(issues))
        (root / 'edit').mkdir(exist_ok=True)
        project.write('edit/edit_plan.json', plan)
        assembly.render(root, plan)
        project.write('goal/render_inputs.json', {'inputs': wanted, 'sha256': sha256(render)})
        return None
    if gate.check(root).status != 'pass':
        return _result('needs_user', goal, assessment, reason='gate_not_pass', next_action=f'cineforge verify {root} --all --attest "<확인 내용>"')
    plan = json.loads((root / 'edit/edit_plan.json').read_text())
    report = final_qa.inspect(root, render, plan=plan)
    if report['status'] != 'pass':
        return _result('blocked', goal, assessment, reason='final_qa_failed', next_action=', '.join(r['id'] for r in report['checks'] if not r['ok']))
    review = project.read('reviews/user_review.json') or {}
    if review.get('render_sha256') != sha256(render):
        return _result('needs_user', goal, assessment, reason='user_approval_missing', next_action=f'cineforge accept {root} final')
    try:
        deliver(root)
    except DeliveryError as exc:
        kind = 'needs_user' if str(exc).startswith('code_motion_playback_required') else 'blocked'
        return _result(kind, goal, assessment, reason=str(exc), next_action=f'cineforge qa-playback {root} --rendered --file <결과.json>' if kind == 'needs_user' else None)
    return None


def _render_inputs(root: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    for rel in ('ssot/scene.json', 'takes/take_registry.json', 'audio/audio_registry.json', 'assets/sound_plan.json'):
        p = root / rel
        h.update(rel.encode() + (hashlib.sha256(p.read_bytes()).digest() if p.is_file() else b'-'))
    return h.hexdigest()


def _external(project: Any, goal: dict[str, Any], assessment: dict[str, Any], stage: str) -> dict[str, Any]:
    """Issue the host hand-off at most once per (revision, stage, input hash)."""
    root = Path(project.root)
    inputs = attempts.input_hash(root)
    key = attempts.attempt_key(goal, f'handoff:{stage}', inputs)
    row = attempts.state(root, key)
    if row and row['status'] == 'started':
        return _result('needs_reconciliation', goal, assessment, reason=key,
                       next_action=f'cineforge goal reconcile {root} {key} --issued|--abandoned')
    if row and row['status'] == 'issued':
        return _result('waiting_external', goal, assessment, reason=stage, request_id=key, next_action=row.get('next_action'))
    attempts.begin(root, key, f'handoff:{stage}', external=True, inputs=inputs, revision=goal['revision'])
    project.run(until=stage)
    live = _stage_state(project, goal, assessment)
    if live and live['state'] in ('needs_user', 'blocked'):
        attempts.record(root, key, 'abandoned')
        return live
    note = (project.progress()['stages'][stage].get('note')) or f'handoffs/{stage}.json'
    attempts.record(root, key, 'issued', next_action=note)
    return _result('waiting_external', goal, assessment, reason=stage, request_id=key, next_action=note)


def drive(root: Path, *, max_actions: int = MAX_ACTIONS) -> dict[str, Any]:
    from .pipeline import Project
    from .project_skills import require_pack

    root = Path(root)
    goal = contract.read(root)
    if goal is None:
        raise contract.GoalError('no goal: run `cineforge goal set` first')
    require_pack(root, allow_mock=goal['kind'] == 'text_storyboard')
    empty = {'unmet': [], 'evidence': {}}
    try:
        lock = attempts.project_lock(root)
        lock.__enter__()
    except attempts.Busy:
        return _result('busy', goal, empty, reason='another drive is running')
    try:
        project = Project(root)
        seen: set[str] = set()
        for _ in range(max_actions):
            assessment = evaluate(root, goal)
            if assessment['satisfied']:
                return _result('satisfied', goal, assessment)
            prog = project.progress()
            fingerprint = json.dumps([assessment['unmet'], {k: v['status'] for k, v in prog['stages'].items()}, attempts.input_hash(root),
                                      (root / 'goal/render_inputs.json').read_text() if (root / 'goal/render_inputs.json').is_file() else ''], sort_keys=True)
            if fingerprint in seen:
                return _stalled(project, goal, assessment)
            seen.add(fingerprint)
            unmet = assessment['unmet']
            if goal['kind'] == 'text_storyboard' or prog['stages']['G2_preproduction_review']['status'] != 'done':
                if (prog['stages']['S06_storyboard']['status'] == 'done' and goal['kind'] == 'text_storyboard'
                        and unmet and all(u.startswith('duration_mismatch') for u in unmet)):
                    if not _fix_duration(project, goal):
                        return _result('blocked', goal, assessment, reason='duration_not_fixable', next_action='컷 길이를 직접 수정하거나 목표 길이를 변경하세요')
                    continue
                until = CEILING.get(goal['kind'], 'G2_preproduction_review')
                project.run(until=until)
                live = _stage_state(project, goal, evaluate(root, goal)) if not evaluate(root, goal)['satisfied'] else None
                if live is not None:
                    return live
                continue
            stop = _post_production(project, goal, assessment, seen)
            if stop is not None:
                return stop
        return _result('blocked', goal, evaluate(root, goal), reason='action_budget_exhausted')
    finally:
        lock.__exit__(None, None, None)


def _stalled(project: Any, goal: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    live = _stage_state(project, goal, assessment)
    return live or _result('blocked', goal, assessment, reason='no_progress: same state after an action')
