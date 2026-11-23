#!/usr/bin/env python3
"""Release guard: the tag matches pyproject's version and user-facing notes exist.

Exit codes: 0 ok, 2 tag/version mismatch, 3 notes missing or without a summary.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_HEADINGS = ("## 요약", "## Summary")


def project_version(root: Path = ROOT) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("pyproject.toml has no version")
    return match.group(1)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: check_release.py vX.Y.Z", file=sys.stderr)
        return 64
    version = project_version()
    tag_version = argv[0].removeprefix("v")
    if tag_version != version:
        print(f"tag {argv[0]} does not match pyproject version {version}", file=sys.stderr)
        return 2
    init = ROOT / "cineforge" / "__init__.py"
    if init.is_file():
        match = re.search(r'^__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"), re.MULTILINE)
        if not match or match.group(1) != version:
            print(f"cineforge/__init__.py version does not match pyproject version {version}", file=sys.stderr)
            return 2
    notes = ROOT / "docs" / "release-notes" / f"{version}.md"
    if not notes.is_file():
        print(f"missing release notes: {notes}", file=sys.stderr)
        return 3
    lines = {line.strip() for line in notes.read_text(encoding="utf-8").splitlines()}
    if not lines.intersection(REQUIRED_HEADINGS):
        print(f"{notes} has no '## 요약' or '## Summary' section", file=sys.stderr)
        return 3
    print(f"release {argv[0]} ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
