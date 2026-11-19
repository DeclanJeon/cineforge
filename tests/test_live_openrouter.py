"""OpenRouter 실호출 테스트(opt-in).

CINEFORGE_LIVE=1 과 OPENROUTER_API_KEY가 모두 있을 때만 돈다. 기본 실행·CI에서는 건너뛴다.
호출당 비용: Jev 1.14 약 $0.00002, 기본 생성 모델(openai/gpt-6.2-sol, $2/$10 per M) 1회 약 $0.005 미만(작은 프롬프트).
    CINEFORGE_LIVE=1 OPENROUTER_API_KEY=... python -m pytest -q tests/test_live_openrouter.py
키는 환경변수에서만 읽고 출력하지 않는다.
"""
import os

import pytest

from cineforge.providers.base import Question
from cineforge.providers.remote import JevOpenRouterDecisionProvider, OpenRouterGenerationProvider

# conftest가 키를 지우기 전에(수집 시점) 읽어 둔다
_ENV = {k: os.environ[k] for k in ("OPENROUTER_API_KEY", "CINEFORGE_GEN_MODEL") if os.environ.get(k)}
LIVE = os.environ.get("CINEFORGE_LIVE") == "1" and "OPENROUTER_API_KEY" in _ENV
pytestmark = pytest.mark.skipif(not LIVE, reason="CINEFORGE_LIVE=1 과 OPENROUTER_API_KEY가 있어야 실호출")


def test_live_jev_decisions():
    p = JevOpenRouterDecisionProvider(env=_ENV)
    qs = [Question("has_reference", "noul", "Does the request name a concrete reference work to imitate?"),
          Question("format", "choice", "Which content format fits best?",
                   {"short_drama": "숏드라마", "documentary": "다큐멘터리", "advertisement": "광고"}),
          Question("fit", "score", "How well do genre and structure fit?", ["poor", "fair", "good"])]
    out = p.ask({"request": "60초 오피스 로맨틱 코미디 숏드라마. 전 여친이 면접관. 결말 선공개."}, qs)
    assert out["format"].value == "short_drama"
    assert out["fit"].value in ("poor", "fair", "good")
    assert 0.0 <= out["has_reference"].value <= 1.0
    assert p.last_usage and p.last_usage.get("cost", 1) < 0.001


def test_live_generation_default_model():
    p = OpenRouterGenerationProvider(env=_ENV)
    out = p.generate("logline", {"title": "면접관이 제 전 여친입니다", "length_chars": 40},
                     {"type": "object", "properties": {"logline": {"type": "string"}}, "required": ["logline"]})
    assert isinstance(out.get("logline"), str) and out["logline"].strip()
