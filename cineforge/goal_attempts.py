"""Project run lock and write-ahead attempt records for the goal driver."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

from .receipts import atomic_text

INPUTS = ('ssot/scene.json', 'ssot/camera.json', 'plan.json', 'authority.json', 'assets/asset_registry.json',
          'takes/take_registry.json', 'audio/audio_registry.json', 'edit/render.mp4', 'reviews/user_review.json')


class Busy(RuntimeError):
    """Another goal drive owns this project."""


def input_hash(root: Path) -> str:
    h = hashlib.sha256()
    for rel in INPUTS:
        p = Path(root) / rel
        h.update(rel.encode() + b'\0' + (hashlib.sha256(p.read_bytes()).digest() if p.is_file() else b'-'))
    return h.hexdigest()[:16]


@contextmanager
def project_lock(root: Path) -> Iterator[None]:
    """OS lock: released automatically when the owning process dies."""
    target = Path(root) / 'goal/lock'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Busy('goal drive already running') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def attempt_key(goal: dict[str, Any], action: str, inputs: str) -> str:
    return hashlib.sha256(f'{goal["revision"]}|{action}|{inputs}'.encode()).hexdigest()[:16]


def _path(root: Path, key: str) -> Path:
    return Path(root) / 'goal/attempts' / f'{key}.json'


def state(root: Path, key: str) -> dict[str, Any] | None:
    p = _path(root, key)
    return json.loads(p.read_text(encoding='utf-8')) if p.is_file() else None


def record(root: Path, key: str, status: str, **fields: Any) -> dict[str, Any]:
    row = {**(state(root, key) or {}), 'key': key, 'status': status, **fields}
    _path(root, key).parent.mkdir(parents=True, exist_ok=True)
    atomic_text(_path(root, key), json.dumps(row, ensure_ascii=False, indent=2))
    return row


def begin(root: Path, key: str, action: str, *, external: bool, inputs: str, revision: int) -> dict[str, Any]:
    """Write intent BEFORE the side effect starts."""
    return record(root, key, 'started', action=action, external=external, input_hash=inputs, goal_revision=revision)


def resolve(root: Path, key: str, outcome: str) -> dict[str, Any]:
    """Operator reconciliation of an uncertain attempt: 'issued' (it was sent) or 'abandoned' (it was not)."""
    row = state(root, key)
    if row is None or row['status'] != 'started':
        raise ValueError(f'no uncertain attempt: {key}')
    if outcome not in ('issued', 'abandoned'):
        raise ValueError('outcome must be issued or abandoned')
    return record(root, key, outcome, reconciled=True)
