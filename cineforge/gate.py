"""Fail-closed delivery gate: only `verified` registries reach final delivery."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

REGISTRIES = (('assets/asset_registry.json', 'asset'), ('audio/audio_registry.json', 'audio'),
              ('takes/take_registry.json', 'take'))
REQUIRED_STATUS = 'verified'


@dataclass(frozen=True, slots=True)
class GateReport:
    status: str
    blockers: tuple[dict[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {'schema_version': 1, 'status': self.status, 'blockers': list(self.blockers)}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(project: Path) -> list[tuple[str, str, dict[str, Any]]]:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for relative, kind in REGISTRIES:
        path = project / relative
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding='utf-8'))
        for row in document.get('assets', document.get('cues', document.get('takes', []))):
            rows.append((kind, row.get('asset_id') or row.get('cue_id') or row.get('take_id'), row))
    return rows


def check(project: Path, *, stage: str = 'delivery') -> GateReport:
    root = Path(project)
    blockers: list[dict[str, str]] = []
    for kind, item, row in _rows(root):
        base = {'item': str(item), 'kind': kind}
        if row.get('status') != REQUIRED_STATUS:
            blockers.append({**base, 'reason': f"not_verified: {row.get('status')}"})
            continue
        relative = row.get('path')
        if not relative:
            blockers.append({**base, 'reason': 'path_missing'})
            continue
        output = root / str(relative)
        if not output.is_file():
            blockers.append({**base, 'reason': 'file_missing'})
            continue
        if row.get('sha256') != _sha(output):
            blockers.append({**base, 'reason': 'hash_mismatch'})
    return GateReport('pass' if not blockers else 'fail', tuple(blockers))


def promote(project: Path, ids: list[str]) -> int:
    """Mark matching rows verified only after the file and hash are re-checked."""
    root = Path(project)
    promoted = 0
    for relative, _kind in REGISTRIES:
        path = root / relative
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding='utf-8'))
        key = 'assets' if 'assets' in document else 'cues' if 'cues' in document else 'takes'
        changed = False
        for row in document[key]:
            item = row.get('asset_id') or row.get('cue_id') or row.get('take_id')
            if item not in ids:
                continue
            output = root / str(row.get('path') or '')
            if row.get('status') == 'verified' or not output.is_file():
                continue
            row.update(status='verified', sha256=_sha(output), promoted_by='user')
            promoted += 1
            changed = True
        if changed:
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
    return promoted
