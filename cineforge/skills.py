"""Locate and diagnose installed CineForge pack adapters without executing them."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .skill_pack_manifest import PackBinding, SkillPackError, read_manifest

DEFAULT_ROOTS = (Path.home() / '.codex/skills', Path.home() / '.pi/agent/skills', Path.home() / '.agents/skills')
MANIFESTS = ('manifest.json', 'video-production-assets/support/manifest.json')


@dataclass(frozen=True)
class InstalledPack:
    root: Path
    binding: PackBinding

    def provenance(self) -> dict[str, str | int]:
        return {**self.binding.identity(), 'root': str(self.root)}


def explicit_root() -> str | None:
    return os.environ.get('CINEFORGE_SKILL_PACK')


def _host_candidates(expected: PackBinding | None) -> tuple[Path, ...]:
    """Active pointer first; a pinned lookup also searches every stored version."""
    from . import skill_store

    pointer = skill_store.read_pointer()
    active = (Path(pointer['root']).expanduser(),) if pointer else ()
    if expected is None:
        return active or DEFAULT_ROOTS
    stored = tuple(skill_store.pack_dir(v) for v in skill_store.installed_versions())
    return (*active, *DEFAULT_ROOTS, *stored)


def discover(root: Path | None = None, *, expected: PackBinding | None = None) -> InstalledPack:
    override = explicit_root()
    if root is None and override is not None:
        if not override.strip():
            raise SkillPackError('invalid', 'CINEFORGE_SKILL_PACK is empty')
        root = Path(override).expanduser()
    candidates = (root,) if root is not None else _host_candidates(expected)
    installed: dict[tuple[str, str], InstalledPack] = {}
    failure = None
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            relative = next((name for name in MANIFESTS if (resolved / name).exists()
                             or (resolved / name).is_symlink()), None)
            if relative is None:
                continue
            binding = read_manifest(resolved, relative)
        except (RuntimeError, OSError) as exc:
            failure = SkillPackError('invalid', f'{candidate}: {exc}')
            continue
        except SkillPackError as exc:
            failure = exc
            continue
        if expected is None or binding == expected:
            installed.setdefault((binding.manifest_sha256, binding.inventory_sha256), InstalledPack(resolved, binding))
    if len(installed) > 1:
        raise SkillPackError('ambiguous', 'set CINEFORGE_SKILL_PACK to one pack root')
    if installed:
        return next(iter(installed.values()))
    if expected is not None:
        detail = f'need {expected.name} {expected.version} ({expected.manifest_sha256}); restore and select it with CINEFORGE_SKILL_PACK'
        raise SkillPackError('invalid', f'{detail}: {failure}' if failure else detail)
    if failure is not None:
        raise failure
    raise SkillPackError('missing', f'no compatible manifest at {root or "the host skill roots"}; set CINEFORGE_SKILL_PACK')


def check(root: Path | None = None) -> dict[str, object]:
    try:
        pack = discover(root)
    except SkillPackError as exc:
        return {'status': exc.status, 'available': False, 'root': str(root) if root else explicit_root(),
                'missing': ['skill_pack'] if exc.status == 'missing' else [], 'pins': {}, 'error': str(exc)}
    return {'status': 'ready', 'available': True, 'missing': [], **pack.provenance(),
            'pins': pack.binding.files}
