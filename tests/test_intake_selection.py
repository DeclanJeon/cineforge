import pytest

from cineforge.intake import FACTORS, analyze, detect_selection
from cineforge.selection import fill_required, interactive, merge, missing_required, new_selection, parse_set_flags, validate
from conftest import SAMPLE_REQUEST


def test_detect_sample_request(tax):
    sel = detect_selection(SAMPLE_REQUEST, tax)
    assert sel["duration"] == "s60"
    assert sel["format"] == "short_drama"
    assert "comedy" in sel["genre"]
    assert sel["narrative"] == "ending_first"
    assert sel["direction"]["texture"] == "cinematic"
    assert sel["direction"]["expression"] == "live_action"


def test_detect_does_not_match_drama_inside_short_drama(tax):
    sel = detect_selection("숏드라마 하나", tax)
    assert sel.get("format") == "short_drama"


def test_analyze_reports_nine_factors(tax, mock_router):
    result = analyze(SAMPLE_REQUEST, mock_router, tax).to_dict()
    assert len(FACTORS) == 9 and set(result["factors"]) == {f["id"] for f in FACTORS}
    assert result["factors"]["direction"]["status"] in ("provided", "partial")
    assert result["factors"]["lead_character"]["status"] == "missing"


def test_no_speech_constraint(tax, mock_router):
    result = analyze("대사 없이 효과음만 있는 30초 영상", mock_router, tax, {"no_speech": True}).to_dict()
    assert "no_speech" in result["constraints"]


def test_set_flags_accept_korean_and_direction(tax):
    patch = parse_set_flags(["narrative=결말 선공개형", "direction.texture=시네마틱", "genre=코미디,로맨스"], tax)
    assert patch["narrative"] == "ending_first"
    assert patch["direction"]["texture"] == "cinematic"
    assert set(patch["genre"]) == {"comedy", "romance"}


def test_set_flags_reject_unknown(tax):
    with pytest.raises((ValueError, KeyError)):
        parse_set_flags(["narrative=없는구조"], tax)


def test_fill_required_non_interactive(tax, mock_router):
    sel = merge(new_selection(), detect_selection(SAMPLE_REQUEST, tax), "request")
    filled = fill_required(sel, SAMPLE_REQUEST, mock_router, tax)
    assert not missing_required(filled, tax)
    assert not validate(filled, tax)
    assert filled["sources"]["duration"] == "request"


def test_interactive_with_scripted_answers(tax, mock_router):
    sel = merge(new_selection(), detect_selection(SAMPLE_REQUEST, tax), "request")
    answers = iter(["1", "?", "!"] + [""] * 200)
    out = interactive(sel, SAMPLE_REQUEST, mock_router, tax, ask=lambda _p: next(answers), printer=lambda *_a: None)
    assert not missing_required(out, tax)
    assert any(v == "ai" for v in out["sources"].values())
    assert out["narrative"] == "ending_first"  # 감지된 값은 유지


def test_speech_is_independent_of_cast(tax, mock_router):
    for name in ("한서윤", "지민"):
        result = analyze(f"주연 {name}, 카페에서 일하는 30초 영상", mock_router, tax).to_dict()
        assert "no_speech" not in result["constraints"]
        assert "ai_persona_disclosure" not in result["constraints"]
        silent = analyze(f"AI 페르소나 주연 {name}, 대사 없음", mock_router, tax).to_dict()
        assert {"no_speech", "ai_persona_disclosure"} <= set(silent["constraints"])
