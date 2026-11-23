"""Request -> verifiable goal contract (goal.json). Ambiguity is never guessed away."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .receipts import atomic_text

KINDS = ('text_storyboard', 'delivery_mp4')
ASPECTS = ('9:16', '16:9', '1:1', '4:5')
_UNSUPPORTED = re.compile(r'이미지\s*(스토리\s*보드|콘티|보드)|그림\s*(콘티|보드)|컷\s*수정|단일\s*컷|게시|업로드|올려')
_BOARD = re.compile(r'스토리\s*보드|콘티|storyboard', re.I)
_BOARD_ONLY = re.compile(r'(스토리\s*보드|콘티|보드)\s*(만|까지만|에서\s*멈)|(영상|mp4|렌더|생성)\w*\s*(은|는)?\s*(만들지|제외|말고|없이|하지)', re.I)
_DELIVERY = re.compile(r'mp4|납품|최종\s*영상|완성본|완성\s*영상|렌더|영상으로\s*(완성|만들)', re.I)
_DURATION = re.compile(r'(\d+(?:\.\d+)?)\s*초')
_ASPECT = re.compile(r'(9\s*:\s*16|16\s*:\s*9|1\s*:\s*1|4\s*:\s*5)')


class GoalError(ValueError):
    """goal.json is invalid or cannot be activated."""


def _constraints(request: str) -> dict[str, Any]:
    found: dict[str, Any] = {}
    if (m := _DURATION.search(request)):
        found['duration_s'] = float(m.group(1))
    if (m := _ASPECT.search(request)):
        found['aspect'] = re.sub(r'\s+', '', m.group(1))
    return found


def resolve(request: str, kind: str | None = None) -> dict[str, Any]:
    """Return {'status': 'resolved', 'goal': ...} or {'status': 'unresolved', 'candidates', 'reason'}."""
    text = (request or '').strip()
    if not text:
        return {'status': 'unresolved', 'candidates': [], 'reason': 'empty_request'}
    forced = kind
    if kind is not None and kind not in KINDS:
        raise GoalError(f'unknown goal kind: {kind}')
    if _UNSUPPORTED.search(text):
        return {'status': 'unresolved', 'candidates': [], 'reason': 'unsupported_scope', 'request': text}
    if kind is None:
        board_only, delivery, board = bool(_BOARD_ONLY.search(text)), bool(_DELIVERY.search(text)), bool(_BOARD.search(text))
        negated_video = bool(re.search(r'(영상|mp4|렌더)\w*\s*(은|는)?\s*(만들지|제외|말고|없이)', text, re.I))
        if board_only and (negated_video or not delivery):
            kind = 'text_storyboard'
        elif delivery and not negated_video:
            kind = 'delivery_mp4'
        elif board and not delivery:
            kind = None
    if kind is None:
        return {'status': 'unresolved', 'candidates': list(KINDS), 'reason': 'ambiguous_deliverable', 'request': text}
    goal = {'version': 1, 'revision': 1, 'kind': kind, 'request': text, 'constraints': _constraints(text),
            'source': 'explicit_kind' if forced else 'explicit_request'}
    validate(goal)
    return {'status': 'resolved', 'goal': goal}


def validate(goal: Any) -> dict[str, Any]:
    if not isinstance(goal, dict) or goal.get('version') != 1:
        raise GoalError('unsupported goal version')
    if goal.get('kind') not in KINDS:
        raise GoalError(f'unknown goal kind: {goal.get("kind")}')
    if type(goal.get('revision')) is not int or goal['revision'] < 1:
        raise GoalError('revision must be a positive integer')
    constraints = goal.get('constraints') or {}
    duration = constraints.get('duration_s')
    if duration is not None and (isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0):
        raise GoalError('duration_s must be positive')
    if constraints.get('aspect') is not None and constraints['aspect'] not in ASPECTS:
        raise GoalError('unsupported aspect')
    return goal


def path(root: Path) -> Path:
    return Path(root) / 'goal.json'


def read(root: Path) -> dict[str, Any] | None:
    target = path(root)
    return validate(json.loads(target.read_text(encoding='utf-8'))) if target.is_file() else None


def write(root: Path, goal: dict[str, Any]) -> dict[str, Any]:
    """Persist a goal; a changed kind/request/constraints bumps the revision."""
    validate(goal)
    current = read(root)
    if current is not None:
        same = all(current[k] == goal[k] for k in ('kind', 'request', 'constraints'))
        goal = {**goal, 'revision': current['revision'] if same else current['revision'] + 1}
    atomic_text(path(root), json.dumps(goal, ensure_ascii=False, indent=2))
    return goal
