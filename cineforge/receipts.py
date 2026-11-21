"""Project-local content pins and atomic checkpoint persistence."""
import hashlib
import os
import tempfile
from pathlib import Path


def pins(root: Path, names: list[str]) -> dict[str, str]:
    root = root.resolve()
    result = {}
    for name in names:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"receipt file unavailable: {name}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        result[str(path.relative_to(root))] = digest.hexdigest()
    return result


def atomic_text(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf8") as f:
        tmp = Path(f.name)
        try:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
