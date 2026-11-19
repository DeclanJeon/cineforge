import json

import pytest

from cineforge.providers.base import AgentInputRequired, ProviderError, Question, parse_jev_answers
from cineforge.providers.remote import (DEFAULT_GEN_MODEL, OPENROUTER_DECISIONS_URL, JevOpenRouterDecisionProvider,
                                        JevTypeSafeDecisionProvider, OpenRouterGenerationProvider)
from cineforge.providers.router import build_router

FAKE_KEY = "sk-test-not-real-0000"
QS = [Question("pick", "choice", "어느 쪽?", {"a": "A", "b": "B"}), Question("q", "score", "품질?", ["10", "50", "90"]),
      Question("has", "noul", "있나?")]


def test_parse_jev_answers_shapes():
    raw = {"answers": {"pick": {"choice": "b", "probabilities": {"b": 0.9}, "confidence": 0.8},
                       "q": {"score": 2}, "has": {"noul": 0.7}}}
    out = parse_jev_answers(raw, QS, "x")
    assert out["pick"].value == "b" and out["q"].value == "90" and out["has"].value == pytest.approx(0.7)


def test_parse_rejects_out_of_range():
    with pytest.raises(ProviderError):
        parse_jev_answers({"answers": {"pick": {"choice": "z"}, "q": {"score": "50"}, "has": {"noul": 1}}}, QS, "x")


def test_typesafe_request_shape():
    seen = {}

    def transport(url, headers, body, timeout):
        seen.update(url=url, headers=headers, body=body)
        return {"answers": {"pick": {"choice": "a"}, "q": {"score": "50"}, "has": {"noul": 0.1}}}

    p = JevTypeSafeDecisionProvider(env={"TYPESAFE_API_KEY": FAKE_KEY}, transport=transport)
    out = p.ask({"request": "x"}, QS)
    assert seen["url"].endswith("/v1/systemone")
    assert seen["body"]["model"] == "jev-1.14.0"
    assert set(seen["body"]["questions"]) == {"pick", "q", "has"}
    assert out["pick"].value == "a"


def test_openrouter_jev_falls_back_on_bad_shape(tmp_path):
    def transport(url, headers, body, timeout):
        return {"choices": [{"message": {"content": "그냥 산문입니다"}}]}

    router = build_router("openrouter", io_dir=tmp_path, env={"OPENROUTER_API_KEY": FAKE_KEY}, transport=transport)
    answers = router.decide({"x": 1}, [Question("pick", "choice", "?", {"a": "A", "b": "B"}, hints={"default": "b"})])
    assert answers["pick"].value in ("a", "b")
    assert any(e["provider"] == "jev-openrouter" and e["status"] == "fallback" for e in router.log)
    assert FAKE_KEY not in json.dumps(router.log)


def test_openrouter_jev_uses_decisions_api():
    seen = {}

    def transport(url, headers, body, timeout):
        seen.update(url=url, body=body)
        # 2026-11-19 실호출 응답 형태(값만 축약)
        return {"model": "typesafe/jev-1.14-20261014", "provider": "TypeSafe", "id": "gen-dec-x",
                "answers": {"pick": {"type": "choice", "choice": "a", "probabilities": {"a": 1, "b": 0}, "confidence": 1}},
                "usage": {"input_tokens": 452, "output_tokens": 78, "cost": 1.8984e-05}}

    p = JevOpenRouterDecisionProvider(env={"OPENROUTER_API_KEY": FAKE_KEY}, transport=transport)
    assert p.ask({}, [QS[0]])["pick"].value == "a"
    assert seen["url"] == OPENROUTER_DECISIONS_URL == "https://openrouter.ai/api/alpha/decisions"
    assert seen["body"]["model"] == "typesafe/jev-1.14"
    assert set(seen["body"]) == {"model", "state", "questions"}
    assert seen["body"]["questions"]["pick"] == {"type": "choice", "instructions": "어느 쪽?", "criteria": {"a": "A", "b": "B"}}
    assert p.last_usage["cost"] == pytest.approx(1.8984e-05)


def test_score_continuous_value_maps_to_level():
    # 실제 Jev는 score를 0..N-1 연속값 + 버킷 확률로 준다
    raw = {"answers": {"q": {"type": "score", "score": 1.71, "probabilities": {"0": 0.05, "1": 0.2, "2": 0.75}}}}
    assert parse_jev_answers(raw, [QS[1]], "x")["q"].value == "90"
    assert parse_jev_answers({"answers": {"q": {"score": 0.6}}}, [QS[1]], "x")["q"].value == "50"
    with pytest.raises(ProviderError):
        parse_jev_answers({"answers": {"q": {"score": 7.2}}}, [QS[1]], "x")


def test_refusal_is_not_an_answer():
    with pytest.raises(ProviderError):
        parse_jev_answers({"answers": {"has": {"type": "refusal"}}}, [QS[2]], "x")


def test_generation_default_model_and_override():
    p = OpenRouterGenerationProvider(env={"OPENROUTER_API_KEY": FAKE_KEY})
    assert p.available() and p.model == DEFAULT_GEN_MODEL == "openai/gpt-6.1-terra"
    assert OpenRouterGenerationProvider(env={"OPENROUTER_API_KEY": FAKE_KEY, "CINEFORGE_GEN_MODEL": "some/model"}).model == "some/model"
    assert not OpenRouterGenerationProvider(env={"OPENROUTER_API_KEY": FAKE_KEY, "CINEFORGE_GEN_MODEL": "off"}).available()
    assert not OpenRouterGenerationProvider(env={}).available()  # 키 없으면 절대 호출 안 함


def test_generation_request_shape():
    seen = {}

    def transport(url, headers, body, timeout):
        seen.update(url=url, body=body)
        return {"choices": [{"message": {"content": "{\"title\": \"면접관이 제 전 여친입니다\"}"}}], "usage": {"cost": 0.001}}

    p = OpenRouterGenerationProvider(env={"OPENROUTER_API_KEY": FAKE_KEY}, transport=transport)
    assert p.generate("title", {"x": 1})["title"].startswith("면접관")
    assert seen["url"].endswith("/api/v1/chat/completions") and seen["body"]["model"] == DEFAULT_GEN_MODEL
    assert p.last_usage == {"cost": 0.001}


def test_host_agent_roundtrip(tmp_path):
    router = build_router("host", io_dir=tmp_path, env={})
    with pytest.raises(AgentInputRequired) as exc:
        router.decide({"x": 1}, [QS[0]], task="pick_task")
    req = json.loads(exc.value.request_path.read_text(encoding="utf-8"))
    assert req["kind"] == "decision" and "pick" in req["questions"]
    exc.value.response_path.parent.mkdir(parents=True, exist_ok=True)
    exc.value.response_path.write_text(json.dumps({"answers": {"pick": {"choice": "b"}}}), encoding="utf-8")
    assert router.decide({"x": 1}, [QS[0]], task="pick_task")["pick"].value == "b"


def test_auto_without_keys_is_offline(tmp_path):
    router = build_router("auto", io_dir=tmp_path, env={})
    desc = router.describe()
    avail = [p["name"] for p in desc["decision"] if p["available"]]
    assert avail == ["heuristic"]
    assert [p["name"] for p in desc["generation"] if p["available"]] == ["mock"]


def test_unknown_mode():
    with pytest.raises(ValueError):
        build_router("nope", env={})
