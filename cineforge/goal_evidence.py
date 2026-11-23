"""Read-only completion judgement for a goal. It never writes into the project."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

FPS = 24
ASPECT_CODES = {'r9_16': '9:16', 'r16_9': '16:9', 'r1_1': '1:1', 'r4_5': '4:5'}


def _json(root: Path, rel: str) -> Any:
    target = root / rel
    return json.loads(target.read_text(encoding='utf-8')) if target.is_file() else None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def board_problems(root: Path, goal: dict[str, Any]) -> list[str]:
    scene, camera = _json(root, 'ssot/scene.json'), _json(root, 'ssot/camera.json')
    progress = _json(root, 'progress.json') or {}
    if (progress.get('stages', {}).get('S06_storyboard', {}).get('status')) != 'done' or not scene or not camera:
        return ['storyboard_missing']
    problems: list[str] = []
    cuts = scene['data'].get('cuts') or []
    if not cuts:
        return ['storyboard_empty']
    ids = [c['cut_id'] for c in cuts]
    if len(set(ids)) != len(ids):
        problems.append('duplicate_cut_ids')
    shots = {c['cut_id'] for c in camera['data'].get('cuts', camera['data'].get('shots', []))}
    problems += [f'camera_missing:{i}' for i in ids if i not in shots]
    problems += [f'bad_duration:{c["cut_id"]}' for c in cuts if float(c['duration']) <= 0]
    cursor = 0.0
    for c in cuts:
        if abs(float(c['start']) - cursor) > 0.011:
            problems.append(f'timeline_gap:{c["cut_id"]}')
        cursor = float(c['end'])
    want = goal['constraints'].get('duration_s')
    if want is not None and abs(cursor - float(want)) > 1.0 / FPS + 1e-9:
        problems.append(f'duration_mismatch:{cursor}!={want}')
    aspect = goal['constraints'].get('aspect')
    have = ASPECT_CODES.get((_json(root, 'selection.json') or {}).get('aspect'))
    if aspect and have != aspect:
        problems.append(f'aspect_mismatch:{have}!={aspect}')
    return problems


def delivery_problems(root: Path, goal: dict[str, Any]) -> list[str]:
    from .gate import check

    bundle = _json(root, 'final/delivery.json')
    if not bundle:
        return ['delivery_missing']
    final, render = root / str(bundle.get('video', '')), root / 'edit/render.mp4'
    if not final.is_file():
        return ['final_file_missing']
    problems: list[str] = []
    digest = sha256(final)
    if digest != bundle.get('sha256'):
        problems.append('final_hash_mismatch')
    if not render.is_file() or sha256(render) != digest:
        problems.append('render_differs_from_final')
    review = _json(root, 'reviews/user_review.json') or {}
    if review.get('accepted') is not True or review.get('render_sha256') != digest:
        problems.append('user_approval_not_for_this_render')
    if bundle.get('final_qa') != 'pass':
        problems.append('final_qa_not_pass')
    if check(root).status != 'pass':
        problems.append('gate_not_pass')
    want = goal['constraints'].get('duration_s')
    if want is not None and abs(float(bundle.get('duration', 0)) - float(want)) > 1.0 / FPS + 1e-9:
        problems.append('duration_mismatch')
    aspect = goal['constraints'].get('aspect')
    if aspect:
        w, h = aspect.split(':')
        if int(bundle.get('width', 0)) * int(h) != int(bundle.get('height', 0)) * int(w):
            problems.append('aspect_mismatch')
    return problems


def evaluate(root: Path, goal: dict[str, Any]) -> dict[str, Any]:
    root = Path(root)
    board = board_problems(root, goal)
    unmet = list(board)
    evidence: dict[str, Any] = {'storyboard': not board}
    if goal['kind'] == 'delivery_mp4':
        delivery = delivery_problems(root, goal)
        unmet += delivery
        evidence['delivery'] = not delivery
    return {'satisfied': not unmet, 'unmet': unmet, 'evidence': evidence}
