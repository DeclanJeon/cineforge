"""`cineforge skills` subcommands: list, update (explicit), use; bare command unchanged."""
from __future__ import annotations

import json

import pytest

from cineforge import skill_store
from cineforge.cli import main
from cineforge.skill_pack_manifest import SkillPackError
from conftest import make_skill_pack

INFO = skill_store.ReleaseInfo("2.65", "## 요약\nnew", "https://x/a.tar.gz", "https://x/a.sha256", "2026-12-01")


@pytest.fixture
def fake_remote(monkeypatch):
    installed = []

    def fetch(version, **_):
        return INFO

    def install(info, **_):
        root = make_skill_pack(skill_store.pack_dir(info.version), info.version)
        installed.append(info.version)
        return root

    monkeypatch.setattr(skill_store, "fetch_release", fetch)
    monkeypatch.setattr(skill_store, "install", install)
    return installed


@pytest.fixture
def no_host_pack(monkeypatch):
    from cineforge import skills

    monkeypatch.delenv("CINEFORGE_SKILL_PACK")
    monkeypatch.setattr(skills, "DEFAULT_ROOTS", ())


def run(capsys, *argv):
    code = main(["skills", *argv])
    return code, capsys.readouterr().out


def test_bare_skills_command_unchanged(capsys, fixture_pack):
    code, out = run(capsys)
    report = json.loads(out)
    assert code == 0 and report["status"] == "ready" and "pins" in report
    code, out = run(capsys, "--root", str(fixture_pack))
    assert code == 0 and json.loads(out)["available"] is True


def test_update_check_no_write(capsys, fake_remote, no_host_pack):
    code, out = run(capsys, "update", "--check")
    report = json.loads(out)
    assert code == 0
    assert report == {"current": None, "latest": "2.65", "update_available": True,
                      "notes": "## 요약\nnew", "installed": None}
    assert fake_remote == [] and skill_store.read_pointer() is None


def test_update_requires_yes_noninteractive(capsys, fake_remote, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code, out = run(capsys, "update")
    assert code == 1
    assert fake_remote == [] and skill_store.read_pointer() is None


def test_update_yes_installs_and_points(capsys, fake_remote, no_host_pack):
    code, out = run(capsys, "update", "--yes")
    report = json.loads(out)
    assert code == 0 and report["installed"] == "2.65"
    assert skill_store.read_pointer() == {"version": "2.65", "root": str(skill_store.pack_dir("2.65"))}
    code, out = run(capsys, "list")
    assert json.loads(out) == {"active": "2.65", "installed": ["2.65"]}


def test_update_when_current_is_latest(capsys, fake_remote, no_host_pack):
    run(capsys, "update", "--yes")
    code, out = run(capsys, "update", "--check")
    assert json.loads(out)["update_available"] is False


def test_use_switches_and_rejects_unknown(capsys):
    make_skill_pack(skill_store.pack_dir("2.63"), "2.63")
    code, _ = run(capsys, "use", "9.9")
    assert code == 1 and skill_store.read_pointer() is None
    code, out = run(capsys, "use", "2.63")
    assert code == 0 and skill_store.read_pointer()["version"] == "2.63"


def test_update_network_error_exit_1(capsys, monkeypatch):
    def offline(version, **_):
        raise SkillPackError("network", "offline")

    monkeypatch.setattr(skill_store, "fetch_release", offline)
    code, out = run(capsys, "update", "--check")
    assert code == 1 and json.loads(out)["error"].startswith("skill_pack_network")


def test_env_override_warns_and_reports_current(capsys, fake_remote, monkeypatch, fixture_pack):
    # CINEFORGE_SKILL_PACK is set to the fixture pack (version "fixture") by conftest.
    code, out = run(capsys, "update", "--check")
    report = json.loads(out)
    assert code == 0 and report["current"] == "fixture"
    assert "CINEFORGE_SKILL_PACK" in report["warning"]
    code, out = run(capsys, "update", "--yes")
    assert "CINEFORGE_SKILL_PACK" in json.loads(out)["warning"]


def test_current_falls_back_to_discovered_pack(capsys, fake_remote, monkeypatch, tmp_path):
    from cineforge import skills

    pack = make_skill_pack(tmp_path / "host", "2.64")
    monkeypatch.delenv("CINEFORGE_SKILL_PACK")
    monkeypatch.setattr(skills, "DEFAULT_ROOTS", (pack,))
    code, out = run(capsys, "update", "--check")
    report = json.loads(out)
    assert report["current"] == "2.64" and "warning" not in report


def test_use_default_removes_pointer(capsys):
    make_skill_pack(skill_store.pack_dir("2.63"), "2.63")
    run(capsys, "use", "2.63")
    code, out = run(capsys, "use", "--default")
    assert code == 0 and skill_store.read_pointer() is None
