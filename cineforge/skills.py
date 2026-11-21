"""Skill-pack readiness: pin the installed tool bytes a delivery relied on."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

REQUIRED = (
    'creative-production/SKILL.md',
    'video-production-assets/scripts/render_sequence.py',
    'video-production-assets/scripts/sequence_media.py',
    'video-production-assets/scripts/sequence_contract.py',
    'video-production-assets/scripts/validate_sequence.py',
    'video-production-assets/scripts/update_project.py',
    'camera-spatial-design/scripts/spatial_spec.py',
    'recording-production-history/scripts/production_history.py',
)
DEFAULT_ROOTS = (Path.home() / '.codex/skills', Path.home() / '.pi/agent/skills', Path.home() / '.agents/skills')


def discover() -> Path | None:
    override = os.environ.get('CINEFORGE_SKILL_PACK')
    candidates = [Path(override)] if override else list(DEFAULT_ROOTS)
    for root in candidates:
        if (root / 'creative-production/SKILL.md').is_file() and (root / 'video-production-assets').is_dir():
            return root
    return None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root: Path | None = None) -> dict[str, Any]:
    pack = Path(root) if root else discover()
    if pack is None:
        return {'available': False, 'root': None, 'missing': ['skill_pack'], 'pins': {}}
    missing = [name for name in REQUIRED if not (pack / name).is_file()]
    pins = {} if missing else {name: _sha(pack / name) for name in REQUIRED}
    return {'available': not missing, 'root': str(pack), 'missing': missing, 'pins': pins}


def pins(root: Path | None = None) -> dict[str, str]:
    return check(root)['pins']
