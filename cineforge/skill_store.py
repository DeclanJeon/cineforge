"""Verified local store of published skill packs (explicit, user-run updates only).

Layout: ``<data>/cineforge/skill-packs/contents-production-skills-<version>/`` per
version, never deleted here, plus an active pointer ``<config>/cineforge/skill-pack.json``.
Projects keep their own pins; changing the active pack only affects new projects.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from .skill_pack_manifest import SkillPackError, read_manifest

REPO = "DeclanJeon/contents-production-skills"
API = f"https://api.github.com/repos/{REPO}/releases"
PACK_NAME = "contents-production-skills"
TIMEOUT = 60

Opener = Callable[..., object]


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    notes: str
    archive_url: str
    sha256_url: str
    published: str


def _base(env: str, fallback: str) -> Path:
    value = os.environ.get(env)
    return Path(value).expanduser() if value else Path.home() / fallback


def store_root() -> Path:
    return _base("XDG_DATA_HOME", ".local/share") / "cineforge" / "skill-packs"


def pointer_path() -> Path:
    return _base("XDG_CONFIG_HOME", ".config") / "cineforge" / "skill-pack.json"


def pack_dir(version: str) -> Path:
    return store_root() / f"{PACK_NAME}-{version}"


def read_pointer() -> dict | None:
    path = pointer_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and isinstance(data.get("version"), str) and isinstance(data.get("root"), str):
        return {"version": data["version"], "root": data["root"]}
    return None


def write_pointer(version: str, root: Path) -> None:
    path = pointer_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"version": version, "root": str(root)}, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _version_key(version: str) -> tuple:
    return tuple(int(p) if p.isdigit() else -1 for p in version.split("."))


def installed_versions() -> list[str]:
    store = store_root()
    if not store.is_dir():
        return []
    prefix = f"{PACK_NAME}-"
    found = [p.name[len(prefix):] for p in store.iterdir()
             if p.is_dir() and not p.is_symlink() and p.name.startswith(prefix) and not p.name.endswith(".partial")]
    return sorted(found, key=_version_key, reverse=True)


def _open(opener: Opener, url: str) -> bytes:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "cineforge-skill-store"})
    try:
        with opener(request, timeout=TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise SkillPackError("missing", f"{url}: not found") from exc
        raise SkillPackError("network", f"{url}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise SkillPackError("network", f"{url}: {exc}") from exc


def fetch_release(version: str | None, *, opener: Opener = urllib.request.urlopen) -> ReleaseInfo:
    url = f"{API}/latest" if version is None else f"{API}/tags/v{version.removeprefix('v')}"
    try:
        data = json.loads(_open(opener, url))
    except ValueError as exc:
        raise SkillPackError("network", f"{url}: invalid JSON") from exc
    tag = str(data.get("tag_name", ""))
    found = tag.removeprefix("v")
    archive = f"{PACK_NAME}-{found}.tar.gz"
    checksum = f"{PACK_NAME}-{found}.sha256"
    assets = {a.get("name"): a.get("browser_download_url") for a in data.get("assets", [])}
    if not assets.get(archive) or not assets.get(checksum):
        raise SkillPackError("missing", f"release {tag} has no {archive} with {checksum}")
    return ReleaseInfo(found, str(data.get("body") or ""), assets[archive], assets[checksum],
                       str(data.get("published_at") or ""))


def _check_members(tar: tarfile.TarFile, prefix: str) -> None:
    for member in tar.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SkillPackError("unsafe", f"archive member escapes its folder: {member.name}")
        if path.parts[:1] != (prefix,):
            raise SkillPackError("unsafe", f"archive member outside {prefix}/: {member.name}")
        if not (member.isfile() or member.isdir()):
            raise SkillPackError("unsafe", f"archive member is not a plain file or folder: {member.name}")


def _validate(root: Path) -> None:
    from .skills import MANIFESTS

    relative = next((name for name in MANIFESTS if (root / name).is_file()), None)
    if relative is None:
        raise SkillPackError("invalid", f"{root.name} has no CineForge pack manifest")
    read_manifest(root, relative)


def install(info: ReleaseInfo, *, opener: Opener = urllib.request.urlopen) -> Path:
    target = pack_dir(info.version)
    if target.is_dir():
        return target
    prefix = target.name
    store = store_root()
    partial = store / f"{prefix}.partial"
    with tempfile.TemporaryDirectory(prefix="cineforge-pack-") as tmp:
        archive = Path(tmp) / f"{prefix}.tar.gz"
        archive.write_bytes(_open(opener, info.archive_url))
        expected = _open(opener, info.sha256_url).decode("utf-8", "replace").split()
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if not expected or expected[0].lower() != actual:
            raise SkillPackError("integrity", f"{archive.name}: sha256 {actual} does not match the published checksum")
        try:
            with tarfile.open(archive, "r:gz") as tar:
                _check_members(tar, prefix)
                store.mkdir(parents=True, exist_ok=True)
                shutil.rmtree(partial, ignore_errors=True)
                partial.mkdir()
                extra = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
                for member in tar.getmembers():
                    tar.extract(member, partial, set_attrs=False, **extra)
        except tarfile.TarError as exc:
            shutil.rmtree(partial, ignore_errors=True)
            raise SkillPackError("integrity", f"{archive.name}: {exc}") from exc
        except BaseException:
            shutil.rmtree(partial, ignore_errors=True)
            raise
    try:
        _validate(partial / prefix)
        os.replace(partial / prefix, target)
    finally:
        shutil.rmtree(partial, ignore_errors=True)
    return target
