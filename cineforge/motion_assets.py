"""Approved local assets for the motion lane: explicit, hashed, project-relative."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REGISTRY = 'assets/motion_assets.json'
MAX_BYTES = 12 * 1024 * 1024


def load(root: Path, asset_id: str) -> Path:
    ledger = root/REGISTRY
    if not ledger.is_file():
        raise ValueError(f'motion asset is not registered: {asset_id}')
    registry = json.loads(ledger.read_text())
    row = (registry.get('assets') or {}).get(asset_id)
    if not isinstance(row, dict):
        raise ValueError(f'motion asset is not registered: {asset_id}')
    path = (root/row.get('path', '')).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'motion asset path is missing or outside the project: {asset_id}')
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f'motion asset exceeds {MAX_BYTES} bytes: {asset_id}')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != str(row.get('sha256', '')).lower():
        raise ValueError(f'motion asset hash mismatch: {asset_id}')
    if path.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
        raise ValueError('motion assets must be PNG or JPEG')
    return path
