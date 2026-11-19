from cineforge.concept import blocking, build_concept, compatibility, direction_rules
from cineforge.intake import detect_selection
from cineforge.selection import fill_required, merge, new_selection
from conftest import SAMPLE_REQUEST


def _sel(tax, router, **patch):
    sel = merge(new_selection(), detect_selection(SAMPLE_REQUEST, tax), "request")
    sel = merge(sel, patch, "user")
    return fill_required(sel, SAMPLE_REQUEST, router, tax)


def test_sample_concept_go(tax, mock_router):
    concept = build_concept(_sel(tax, mock_router), tax, mock_router)
    assert concept["concept"]["title_line"].startswith("60초 코미디 숏드라마")
    assert concept["evaluation"]["verdict"] in ("go", "revise")
    assert set(concept["evaluation"]["scores"]) == {"hook", "feasibility", "emotion", "originality", "coherence", "platform_fit"}
    assert concept["candidates"]


def test_15s_complex_narrative_is_flagged(tax, mock_router):
    sel = _sel(tax, mock_router, duration="s15", narrative="parallel")
    issues = compatibility(sel)
    assert issues and any(i["severity"] in ("error", "warn") for i in issues)


def test_override_unblocks(tax, mock_router):
    sel = _sel(tax, mock_router, production_method="stickman_method", direction={"texture": "photoreal"})
    errs = blocking(compatibility(sel))
    assert [e["rule"] for e in errs] == ["C001"]
    sel["overrides"] = ["C001"]
    assert not blocking(compatibility(sel))


def test_1990s_korean_melodrama_rules(tax, mock_router):
    preset = tax.presets["kdrama_1998_timeslip"]["selection"]
    sel = fill_required(merge(new_selection(), preset, "preset"), "", mock_router, tax)
    rules = direction_rules(sel)
    assert "D_kr_melo_1990s" in rules["applied"]
    assert "스마트폰" in rules["forbidden_props"]


def test_no_speech_conflicts_with_dialogue_direction(tax, mock_router):
    sel = _sel(tax, mock_router)
    sel["constraints"] = ["no_speech"]
    sel["direction"]["sound"] = "dialogue_driven"
    assert any(i["rule"] == "C100" for i in compatibility(sel))
