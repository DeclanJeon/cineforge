import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cineforge.providers.router import build_router  # noqa: E402
from cineforge.taxonomy import Taxonomy  # noqa: E402

SECRET_VARS = ("OPENROUTER_API_KEY", "TYPESAFE_API_KEY", "CINEFORGE_GEN_MODEL", "CINEFORGE_AGENT_MODE")


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch):
    """모든 테스트는 오프라인: 실제 키가 환경에 있어도 지운다(유료 호출 방지)."""
    for var in SECRET_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(scope="session")
def tax():
    return Taxonomy()


@pytest.fixture
def mock_router(tmp_path):
    return build_router("mock", io_dir=tmp_path / "agent_io", env={})


@pytest.fixture(scope="session")
def example_plan():
    return json.loads((ROOT / "examples/plans/interviewer-ex-girlfriend.plan.json").read_text(encoding="utf-8"))


SAMPLE_REQUEST = ("60초 분량의 코미디 숏드라마 콘텐츠를 기획해줘. 연출은 시네마틱 실사, 서사 구조는 결말 선공개으로 하고 "
                  "시놉시스, 후킹, 타임라인, 씬과 컷 구성까지")
