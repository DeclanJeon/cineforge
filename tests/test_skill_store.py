"""Verified skill-pack store: checksum, safe extraction, contract check, pointer."""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
import urllib.error
from pathlib import Path

import pytest

from cineforge import skill_store
from cineforge.skill_pack_manifest import SkillPackError
from conftest import make_skill_pack

PREFIX = "contents-production-skills-2.64"
API = "https://api.github.com/repos/DeclanJeon/contents-production-skills/releases"
ARCHIVE_URL = f"https://example.test/{PREFIX}.tar.gz"
SHA_URL = f"https://example.test/{PREFIX}.sha256"


@pytest.fixture(autouse=True)
def xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


def pack_archive(tmp_path: Path, version: str = "2.64") -> bytes:
    root = make_skill_pack(tmp_path / "src" / f"contents-production-skills-{version}", version)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(root, arcname=root.name)
    return buf.getvalue()


def evil_archive(add) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        add(tar)
    return buf.getvalue()


def file_member(tar: tarfile.TarFile, name: str, data: bytes = b"x") -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def opener_for(archive: bytes, *, digest: str | None = None, version: str = "2.64"):
    digest = digest or hashlib.sha256(archive).hexdigest()
    release = {
        "tag_name": f"v{version}", "body": "## 요약\nnotes", "published_at": "2026-11-24T00:00:00Z",
        "assets": [
            {"name": f"contents-production-skills-{version}.tar.gz", "browser_download_url": ARCHIVE_URL},
            {"name": f"contents-production-skills-{version}.sha256", "browser_download_url": SHA_URL},
        ],
    }
    calls = []

    def opener(request, timeout=None):
        url = request if isinstance(request, str) else request.full_url
        calls.append(url)
        if url.startswith(API):
            return FakeResponse(json.dumps(release).encode())
        if url == ARCHIVE_URL:
            return FakeResponse(archive)
        if url == SHA_URL:
            return FakeResponse(f"{digest}  contents-production-skills-{version}.tar.gz\n".encode())
        raise urllib.error.URLError(f"unexpected {url}")

    opener.calls = calls
    return opener


def test_fetch_release_reads_latest(tmp_path):
    info = skill_store.fetch_release(None, opener=opener_for(pack_archive(tmp_path)))
    assert info.version == "2.64"
    assert info.archive_url == ARCHIVE_URL and info.sha256_url == SHA_URL
    assert info.notes == "## 요약\nnotes"


def test_fetch_release_uses_tag_for_version(tmp_path):
    opener = opener_for(pack_archive(tmp_path))
    skill_store.fetch_release("2.64", opener=opener)
    assert opener.calls[0] == f"{API}/tags/v2.64"


def test_install_verifies_and_extracts(tmp_path):
    opener = opener_for(pack_archive(tmp_path))
    root = skill_store.install(skill_store.fetch_release(None, opener=opener), opener=opener)
    assert root == skill_store.store_root() / PREFIX
    assert (root / "manifest.json").is_file()
    assert skill_store.installed_versions() == ["2.64"]


def test_install_is_idempotent(tmp_path):
    opener = opener_for(pack_archive(tmp_path))
    info = skill_store.fetch_release(None, opener=opener)
    first = skill_store.install(info, opener=opener)
    downloads = len(opener.calls)
    assert skill_store.install(info, opener=opener) == first
    assert len(opener.calls) == downloads


def test_hash_mismatch_installs_nothing(tmp_path):
    opener = opener_for(pack_archive(tmp_path), digest="0" * 64)
    info = skill_store.fetch_release(None, opener=opener)
    with pytest.raises(SkillPackError) as err:
        skill_store.install(info, opener=opener)
    assert err.value.status == "integrity"
    assert not skill_store.store_root().exists() or not any(skill_store.store_root().iterdir())


@pytest.mark.parametrize("add", [
    lambda tar: file_member(tar, f"{PREFIX}/../escape.txt"),
    lambda tar: file_member(tar, "/etc/escape.txt"),
    lambda tar: file_member(tar, "other-top/file.txt"),
], ids=["traversal", "absolute", "wrong-prefix"])
def test_rejects_unsafe_paths(add):
    archive = evil_archive(add)
    opener = opener_for(archive)
    with pytest.raises(SkillPackError) as err:
        skill_store.install(skill_store.fetch_release(None, opener=opener), opener=opener)
    assert err.value.status == "unsafe"
    assert not skill_store.store_root().exists() or not any(skill_store.store_root().iterdir())


def test_rejects_symlink_member():
    def add(tar):
        info = tarfile.TarInfo(f"{PREFIX}/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)

    opener = opener_for(evil_archive(add))
    with pytest.raises(SkillPackError) as err:
        skill_store.install(skill_store.fetch_release(None, opener=opener), opener=opener)
    assert err.value.status == "unsafe"


def test_rejects_archive_without_contract():
    opener = opener_for(evil_archive(lambda tar: file_member(tar, f"{PREFIX}/README.md")))
    with pytest.raises(SkillPackError):
        skill_store.install(skill_store.fetch_release(None, opener=opener), opener=opener)
    assert skill_store.installed_versions() == []


def test_network_failure_leaves_state():
    def offline(request, timeout=None):
        raise urllib.error.URLError("offline")

    with pytest.raises(SkillPackError) as err:
        skill_store.fetch_release(None, opener=offline)
    assert err.value.status == "network"
    assert skill_store.read_pointer() is None


def test_pointer_roundtrip(tmp_path):
    skill_store.write_pointer("2.64", tmp_path / "p")
    assert skill_store.read_pointer() == {"version": "2.64", "root": str(tmp_path / "p")}
    assert skill_store.pointer_path().parent.name == "cineforge"


def test_installed_versions_sorted_and_ignores_other_entries(tmp_path):
    store = skill_store.store_root()
    for name in ("contents-production-skills-2.9", "contents-production-skills-2.64",
                 "contents-production-skills-2.65.partial", "notes"):
        (store / name).mkdir(parents=True)
    (store / "current").symlink_to(store / "contents-production-skills-2.64")
    assert skill_store.installed_versions() == ["2.64", "2.9"]
