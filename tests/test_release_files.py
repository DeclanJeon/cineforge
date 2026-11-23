"""Every released tag has user-facing notes; the release check guards tag/version/notes."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "docs" / "release-notes"


def _tags() -> list[str]:
    out = subprocess.run(["git", "tag", "--list", "v*"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [t.removeprefix("v") for t in out.stdout.split()]


def test_every_tag_has_notes():
    tags = _tags()
    assert tags, "no release tags found"
    for version in tags:
        text = (NOTES / f"{version}.md").read_text(encoding="utf-8")
        lines = {line.strip() for line in text.splitlines()}
        assert "## 요약" in lines and "## Summary" in lines, version


def test_changelog_lists_every_tag():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = {line.split()[1] for line in text.splitlines() if line.startswith("## ")}
    for version in _tags():
        assert version in headings, version


def _check(tag: str, root: Path = ROOT) -> int:
    return subprocess.run([sys.executable, str(root / "scripts" / "check_release.py"), tag],
                          cwd=root, capture_output=True, text=True).returncode


def test_check_release_exit_codes(tmp_path):
    version = next(line.split('"')[1] for line in (ROOT / "pyproject.toml").read_text().splitlines()
                   if line.startswith("version"))
    assert _check(f"v{version}") == 0
    assert _check("v9.9.9") == 2
    copy = tmp_path / "repo"
    (copy / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "check_release.py", copy / "scripts")
    shutil.copy(ROOT / "pyproject.toml", copy)
    assert _check(f"v{version}", copy) == 3
