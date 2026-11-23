"""Fail-closed parser for the declarative CineForge pack contract (no optional dependency)."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .data_loader import load
from .receipts import pins

Status = Literal['missing', 'incompatible', 'invalid', 'ambiguous', 'network', 'integrity', 'unsafe']
FACTS = ('cut_revision', 'code_motion', 'realtime_3d')
INVENTORY = 'integrations/cineforge/files.json'
CONTRACT_VERSION = 1
STAGES = frozenset(row['id'] for row in load('pipeline.yaml')['stages'])


class SkillPackError(ValueError):
    def __init__(self, status: Status, detail: str) -> None:
        self.status = status
        super().__init__(f'skill_pack_{status}: {detail}')


@dataclass(frozen=True)
class StageBinding:
    route: str | None
    owners: tuple[str, ...]
    refs: tuple[str, ...]
    guide: str | None
    when: dict[str, tuple[str, ...]]

    def references(self, facts: set[str]) -> list[str]:
        return list(dict.fromkeys((*self.refs, *(p for fact in FACTS if fact in facts for p in self.when.get(fact, ())))))


@dataclass(frozen=True)
class PackBinding:
    name: str
    version: str
    manifest_sha256: str
    inventory_sha256: str
    stages: dict[str, StageBinding]
    files: dict[str, str]
    delivery_files: tuple[str, ...]

    def identity(self) -> dict[str, str | int]:
        return {'name': self.name, 'version': self.version, 'contract_version': CONTRACT_VERSION,
                'manifest_sha256': self.manifest_sha256, 'inventory_sha256': self.inventory_sha256}

    def document(self) -> dict[str, object]:
        return {**asdict(self), 'mode': 'bound', 'contract_version': CONTRACT_VERSION}


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SkillPackError('invalid', f'duplicate key: {key}')
        result[key] = value
    return result


def read_object(path: Path) -> tuple[dict[str, object], str]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw, object_pairs_hook=_unique)
    except (OSError, UnicodeError, ValueError) as exc:
        raise SkillPackError('invalid', f'{path}: {exc}') from exc
    return mapping(value, str(path)), hashlib.sha256(raw).hexdigest()


def mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SkillPackError('invalid', f'{field}: expected a JSON object')
    return value


def _array(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise SkillPackError('invalid', f'{field}: expected an array of nonempty strings')
    if len(value) != len(set(value)):
        raise SkillPackError('invalid', f'{field}: duplicate entries')
    return tuple(value)


def _str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SkillPackError('invalid', f'{field}: expected nonempty text')
    return value


def _keys(row: dict[str, object], field: str, *, required: set[str], optional: tuple[str, ...] = ()) -> None:
    if not required <= row.keys() or row.keys() - required - set(optional):
        raise SkillPackError('invalid', f'{field}: missing or unsupported fields')


def _relative(name: str) -> str:
    if (any(part in {'', '.', '..'} for part in name.split('/')) or '\\' in name or ':' in name
            or any(ord(ch) < 32 for ch in name)):
        raise SkillPackError('invalid', f'unsafe pack path: {name!r}')
    return name


def pack_file(root: Path, name: str) -> Path:
    try:
        path = (root / _relative(name)).resolve()
    except (OSError, RuntimeError) as exc:
        raise SkillPackError('invalid', f'invalid pack path: {name}: {exc}') from exc
    if not path.is_relative_to(root) or not path.is_file():
        raise SkillPackError('invalid', f'missing or outside pack: {name}')
    return path


def _stage(value: object, sid: str, *, normalized: bool) -> StageBinding:
    row = mapping(value, sid)
    _keys(row, sid, required={'route', 'owners', 'refs'}, optional=('guide', 'when'))
    route = None if row['route'] is None else _str(row['route'], f'{sid}.route')
    owners = _array(row['owners'], f'{sid}.owners')
    if not owners or any(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', owner) is None for owner in owners):
        raise SkillPackError('invalid', f'{sid}: invalid owner ID')
    refs = _array(row['refs'], f'{sid}.refs')
    guide = row.get('guide')
    if guide is not None or ('guide' in row and not normalized):
        guide = _str(guide, f'{sid}.guide')
    when = mapping(row.get('when', {}), f'{sid}.when')
    _keys(when, f'{sid}.when', required=set(), optional=FACTS)
    variants = {}
    for fact, values in when.items():
        if not normalized:
            bundle = mapping(values, f'{sid}.{fact}')
            _keys(bundle, f'{sid}.{fact}', required={'refs'})
            values = bundle['refs']
        variants[fact] = _array(values, f'{sid}.{fact}.refs')
    return StageBinding(route, owners, refs, guide, variants)


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise SkillPackError('invalid', f'{field}: expected SHA-256')
    return value


def parse_binding(data: dict[str, object], *, normalized: bool = False) -> PackBinding:
    if type(data.get('contract_version')) is not int:
        raise SkillPackError('invalid', 'contract_version: expected an integer')
    if data['contract_version'] != CONTRACT_VERSION:
        raise SkillPackError('incompatible', f'unsupported contract_version {data["contract_version"]} (expected 1)')
    stages = mapping(data.get('stages'), 'stages')
    _keys(stages, 'stages', required=set(STAGES))
    bindings = {sid: _stage(row, sid, normalized=normalized) for sid, row in stages.items()}
    delivery = _array(data.get('delivery_files'), 'delivery_files')
    files = {_relative(path): _digest(digest, path) for path, digest in mapping(data.get('files'), 'inventory').items()}
    required = set(delivery)
    for row in bindings.values():
        required.update(row.references(set(FACTS)))
        required.update(f'{owner}/SKILL.md' for owner in row.owners)
        if row.guide:
            required.add(row.guide)
    for path in sorted(required):
        if _relative(path) not in files:
            raise SkillPackError('invalid', f'path not in pack inventory: {path}')
    return PackBinding(_str(data.get('name'), 'name'), _str(data.get('version'), 'version'),
                       _digest(data.get('manifest_sha256'), 'manifest_sha256'),
                       _digest(data.get('inventory_sha256'), 'inventory_sha256'), bindings, files, delivery)


def _installed_files(root: Path, skills: tuple[str, ...], support_skill: str) -> set[str]:
    ignored_dirs = {'__pycache__', '.pytest_cache', '.git', '.worktrees'}
    support = root / support_skill / 'support'
    reserved = {'manifest.json', 'examples', 'qa', 'CHANGELOG.md'}
    paths = set()

    def fail(exc: OSError) -> None:
        raise SkillPackError('invalid', f'cannot scan pack: {exc}') from exc

    for skill in skills:
        base = root / skill
        if base.is_symlink() or not base.is_dir():
            raise SkillPackError('invalid', f'missing or linked skill: {skill}')
        for directory, folders, files in os.walk(base, onerror=fail):
            parent = Path(directory)
            folders[:] = [name for name in folders if name not in ignored_dirs
                          and not (parent == support and name in reserved)]
            for name in folders + files:
                path = parent / name
                if ((parent == support and name in reserved) or path == support / INVENTORY
                        or path.suffix in {'.pyc', '.pyo'}):
                    continue
                if path.is_symlink():
                    raise SkillPackError('invalid', f'linked skill path: {path.relative_to(root)}')
                if name in files:
                    paths.add(path.relative_to(root).as_posix())
    return paths


def read_manifest(root: Path, relative: str) -> PackBinding:
    manifest_path = pack_file(root, relative)
    manifest, manifest_hash = read_object(manifest_path)
    integrations = mapping(manifest.get('integrations', {}), 'integrations')
    contract = mapping(integrations.get('cineforge'), 'integrations.cineforge')
    if type(contract.get('contract_version')) is int and contract['contract_version'] != CONTRACT_VERSION:
        raise SkillPackError('incompatible', f'unsupported contract_version {contract["contract_version"]} (expected 1)')
    _keys(contract, 'integrations.cineforge', required={'contract_version', 'stages', 'inventory', 'delivery_files'})
    if contract['inventory'] != INVENTORY:
        raise SkillPackError('invalid', f'inventory must be {INVENTORY}')
    inv_file = pack_file(root, (Path(relative).parent / INVENTORY).as_posix())
    files, inventory_hash = read_object(inv_file)
    binding = parse_binding({**contract, 'files': files, 'name': manifest.get('name'), 'version': manifest.get('version'),
                             'manifest_sha256': manifest_hash, 'inventory_sha256': inventory_hash})
    skills = _array(manifest.get('skills'), 'skills')
    if any(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', skill) is None for skill in skills):
        raise SkillPackError('invalid', 'invalid skills ID')
    for row in binding.stages.values():
        if not set(row.owners) <= set(skills):
            raise SkillPackError('invalid', 'stage owner is not registered in skills')
    entries = {f'{skill}/SKILL.md' for skill in skills}
    if not entries <= binding.files.keys() or any(path.split('/')[0] not in skills for path in binding.files):
        raise SkillPackError('invalid', 'inventory must cover registered entrypoints and stay in registered skills')
    support = _str(manifest.get('support_skill', 'video-production-assets'), 'support_skill')
    if support not in skills:
        raise SkillPackError('invalid', 'support_skill is not registered in skills')
    actual = _installed_files(root, skills, support)
    if actual != binding.files.keys():
        mismatch = sorted(actual.symmetric_difference(binding.files))[0]
        raise SkillPackError('invalid', f'pack file set does not match inventory: {mismatch}')
    for path in binding.files:
        pack_file(root, path)
    try:
        observed = pins(root, list(binding.files))
    except (OSError, ValueError) as exc:
        raise SkillPackError('invalid', f'unreadable pack inventory: {exc}') from exc
    if observed != binding.files:
        mismatch = next(path for path, digest in binding.files.items() if observed.get(path) != digest)
        raise SkillPackError('invalid', f'inventory hash mismatch: {mismatch}')
    return binding
