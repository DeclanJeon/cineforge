import json

import pytest

from cineforge.providers.base import AgentInputRequired, ProviderError, Question, parse_jev_answers
from cineforge.providers.remote import JevOpenRouterDecisionProvider, JevTypeSafeDecisionProvider, OpenRouterGenerationProvider
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


def test_openrouter_jev_uses_slug():
    seen = {}

    def transport(url, headers, body, timeout):
        seen.update(body=body)
        return {"choices": [{"message": {"content": json.dumps({"answers": {"pick": {"choice": "a"}}})}}]}

    p = JevOpenRouterDecisionProvider(env={"OPENROUTER_API_KEY": FAKE_KEY}, transport=transport)
    assert p.ask({}, [QS[0]])["pick"].value == "a"
    assert seen["body"]["model"] == "typesafe/jev-1.14"


def test_generation_requires_explicit_model():
    assert not OpenRouterGenerationProvider(env={"OPENROUTER_API_KEY": FAKE_KEY}).available()
    assert OpenRouterGenerationProvider(env={"OPENROUTER_API_KEY": FAKE_KEY, "CINEFORGE_GEN_MODEL": "some/model"}).available()


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
