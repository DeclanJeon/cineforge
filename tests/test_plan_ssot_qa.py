import copy

from cineforge import qa
from cineforge.planner import preflight
from cineforge.render import plan_markdown
from cineforge.schemas import validate
from cineforge.ssot import SSOTStore, build_all, impact


def _ssots(plan, sel=None):
    sel = sel or {"constraints": [], "direction": {}}
    concept = {"concept": {"title_line": plan["title"], "subtitle": plan["meta"]["style"], "chain": "", "emotion_arc": ""},
               "direction_rules": {"applied": []}, "evaluation": {"total": 80, "verdict": "go", "scores": {}}, "compatibility": []}
    return build_all(plan, concept, sel, {})


def _wrap(data):
    return {k: {"data": v, "version": 1} for k, v in data.items()}


def test_example_plan_valid(example_plan):
    assert validate(example_plan, "plan") == []
    assert sum(c["duration"] for s in example_plan["scenes"] for c in s["cuts"]) == 60
    checks = {c["id"]: c["status"] for c in preflight(example_plan)}
    assert checks["P01"] == "pass" and checks["P02"] == "pass"


def test_render_has_seven_sections(example_plan):
    md = plan_markdown(example_plan, None)
    for head in ("1. 시놉시스", "2. 후킹", "3. ", "4. ", "5. ", "6. ", "7. "):
        assert head in md
    assert "합격입니다." in md


def test_ssot_build_and_continuity_clean(example_plan):
    ss = _wrap(_ssots(example_plan))
    assert set(ss) == {"concept", "story", "character", "world", "scene", "camera", "motion", "audio"}
    errors = [i for i in qa.continuity(ss, 60.0) if i["severity"] == "error"]
    assert errors == []


def test_deliberate_prop_discontinuity_detected(example_plan):
    plan = copy.deepcopy(example_plan)
    # 컷 2 시작에 도현의 오른손 펜을 왼손으로 옮겨 연속성 오류를 만든다
    plan["scenes"][0]["cuts"][1]["state"] = {"start": {"holding": {"CH01": {"left": "펜"}}}}
    ss = _wrap(_ssots(plan))
    issues = qa.continuity(ss, 60.0)
    assert any(i["rule"] == "CQ02" and i["target"] == "S01C02" for i in issues)


def test_timing_mismatch_detected(example_plan):
    plan = copy.deepcopy(example_plan)
    plan["scenes"][0]["cuts"][0]["duration"] = 5
    ss = _wrap(_ssots(plan))
    assert any(i["rule"] == "CQ01" for i in qa.continuity(ss, 60.0))


def test_forbidden_prop_and_no_speech(example_plan):
    plan = copy.deepcopy(example_plan)
    plan["scenes"][1]["cuts"][0]["visual"] += " 스마트폰을 확인"
    data = _ssots(plan)
    data["concept"]["forbidden_props"] = ["스마트폰"]
    ss = _wrap(data)
    issues = qa.constraints(ss, [], silent=False, no_speech=True)
    rules = {i["rule"]: i["severity"] for i in issues}
    assert rules.get("CQ10") == "error" and rules.get("CQ11") == "error"


def test_ssot_versioning_and_lock(tmp_path, example_plan):
    store = SSOTStore(tmp_path)
    data = _ssots(example_plan)
    doc, changed = store.write("story", data["story"])
    assert changed and doc["version"] == 1
    doc, changed = store.write("story", data["story"])
    assert not changed and doc["version"] == 1
    data["story"]["logline"] = "바뀐 로그라인"
    doc, changed = store.write("story", data["story"])
    assert changed and doc["version"] == 2
    store.set_lock("story", True)
    data["story"]["logline"] = "또 바뀜"
    try:
        store.write("story", data["story"])
        raise AssertionError("잠금 무시됨")
    except PermissionError:
        pass


def test_impact_chain():
    affected = impact("character")
    assert "scene" in affected or "motion" in affected or "prompts" in affected
    assert impact("concept")[0] == "story"
