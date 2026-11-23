"""Project skill-pack lifecycle and provenance; never selects a replacement for a pin."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from .data_loader import load
from .skill_pack_manifest import PackBinding, SkillPackError, parse_binding, read_object
from .skills import InstalledPack, discover, explicit_root

LOCK = 'skill_pack.lock.json'
MODE = 'skill_pack_mode'
LOCK_HASH = 'skill_pack_lock_sha256'


def initial_binding(provider: str) -> PackBinding | None:
    try:
        return discover().binding
    except SkillPackError as exc:
        if provider == 'mock' and exc.status == 'missing' and explicit_root() is None:
            return None
        raise


def lock_text(binding: PackBinding) -> str:
    return json.dumps(binding.document(), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def project_binding(root: Path) -> PackBinding | Literal['legacy', 'mock']:
    meta = root / 'project.json'
    data = read_object(meta)[0] if meta.is_file() else {}
    mode = data.get(MODE)
    lock = root / LOCK
    if mode not in (None, 'bound', 'mock'):
        raise SkillPackError('invalid', f'unsupported project binding mode: {mode}')
    if mode != 'bound':
        if lock.exists() or lock.is_symlink():
            raise SkillPackError('invalid', f'unexpected {LOCK}')
        return 'mock' if mode == 'mock' else 'legacy'
    if lock.is_symlink() or not lock.is_file():
        raise SkillPackError('invalid', f'missing or linked project {LOCK}')
    record, digest = read_object(lock)
    if data.get(LOCK_HASH) != digest or record.get('mode') != 'bound':
        raise SkillPackError('invalid', f'project {LOCK} changed')
    return parse_binding(record, normalized=True)


def require_pack(root: Path, *, allow_mock: bool = False) -> InstalledPack | None:
    saved = project_binding(root)
    if isinstance(saved, PackBinding):
        return discover(expected=saved)
    if saved == 'mock' and not allow_mock:
        raise SkillPackError('missing', 'unbound mock is structure-only; create a new project with a compatible skill pack')
    return None


def display_pipeline(saved: PackBinding | Literal['legacy', 'mock']) -> dict[str, Any]:
    pipeline = dict(load('pipeline.yaml'))
    if isinstance(saved, PackBinding):
        pipeline['stages'] = [{**stage, 'skills': list(saved.stages[stage['id']].owners)} for stage in pipeline['stages']]
    elif saved == 'legacy':
        routes = load('legacy_skill_routes.yaml')
        pipeline['stages'] = [{**stage, **routes[stage['id']]} for stage in pipeline['stages']]
    return pipeline


def provenance(pack: InstalledPack | None) -> dict[str, object]:
    if pack is None:
        return {'mode': 'legacy/unpinned', 'verified_usage': 'unconfirmed'}
    binding = pack.binding
    return {**binding.identity(), 'mode': 'bound', 'verified_usage': 'unconfirmed',
            'delivery_files': {name: binding.files[name] for name in binding.delivery_files}}


def binding_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
