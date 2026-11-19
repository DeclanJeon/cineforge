"""패키지 데이터(YAML) 로더."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=None)
def load(name: str) -> dict[str, Any]:
    with (DATA_DIR / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def data_path(name: str) -> Path:
    return DATA_DIR / name
