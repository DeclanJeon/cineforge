"""Regressions found while producing the 2026-11-24 three-short demo (proof/cineforge-gaps.md)."""
import copy
import json
from pathlib import Path

from cineforge import assets, sound
from cineforge.cli import main
from cineforge.execution_plan import proposal
from cineforge.pipeline import Project
from cineforge.schemas import validate
from cineforge.ssot import build_all
from conftest import SAMPLE_REQUEST


def _concept(plan):
    return {"concept": {"title_line": plan["title"], "subtitle": plan["meta"]["style"], "chain": "", "emotion_arc": ""},
            "direction_rules": {"applied": []}, "evaluation": {"total": 80, "verdict": "go", "scores": {}}, "compatibility": []}


def _ssots(plan, sel=None):
    sel = sel or {"constraints": [], "direction": {}}
    return {k: {"data": v, "version": 1} for k, v in build_all(plan, _concept(plan), sel, {}).items()}


def _narrated(example_plan):
    """A voice-over narrator who is never on screen, plus a cut with nobody in frame."""
    plan = copy.deepcopy(example_plan)
    plan["characters"].append({"id": "NAR", "name": "내레이터", "role": "내레이션", "persona": "차분한 해설자",
                               "appearance": "화면에 나오지 않음", "wardrobe": "해당 없음", "on_screen": False})
    first = plan["scenes"][0]["cuts"][0]
    first.update(speaker="NAR", characters=[])
    return plan


def test_voice_over_character_is_valid_plan_input(example_plan):
    assert validate(_narrated(example_plan), "plan") == []


def test_empty_cut_characters_stays_empty(example_plan):
    ss = _ssots(_narrated(example_plan))
    cut = ss["scene"]["data"]["cuts"][0]
    assert cut["characters"] == []
    frame = assets.frames("p", ss)["frames"][0]
    assert frame["start_frame"]["subjects"] == ""


def test_voice_over_speaker_is_never_placed_on_screen(example_plan):
    plan = _narrated(example_plan)
    plan["scenes"][0]["cuts"][1].update(speaker="NAR")
    plan["scenes"][0]["cuts"][1].pop("characters", None)
    ss = _ssots(plan)
    assert all("NAR" not in c["characters"] for c in ss["scene"]["data"]["cuts"])
    prompts = assets.image_prompts("p", ss, "9:16", "실사")["prompts"]
    assert not [p for p in prompts if p["prompt_id"].startswith("A-NAR")]
    assert "내레이터" not in json.dumps(prompts, ensure_ascii=False)


def test_unspecified_screen_direction_is_not_invented(example_plan):
    plan = copy.deepcopy(example_plan)
    for scene in plan["scenes"]:
        for cut in scene["cuts"]:
            cut.pop("screen_direction", None)
    ss = _ssots(plan)
    video = assets.video_prompts("p", ss, "9:16", False)["prompts"]
    assert all("L→R" not in p["prompt"] for p in video)
    assert all(c["direction"] is None for c in ss["motion"]["data"]["cuts"])


def test_explicit_screen_direction_is_kept(example_plan):
    plan = copy.deepcopy(example_plan)
    plan["scenes"][0]["cuts"][0]["screen_direction"] = "R→L"
    ss = _ssots(plan)
    assert "방향 R→L" in assets.video_prompts("p", ss, "9:16", False)["prompts"][0]["prompt"]


def test_narration_led_short_has_no_vocal_song(example_plan):
    sel = {"constraints": [], "direction": {"sound": "narration_driven"}}
    cues = _ssots(example_plan, sel)["audio"]["data"]["cues"]
    assert not [c for c in cues if c["type"] in ("OST", "BGM") and c["vocal"]]
    assert all(t["vocal"] is False for t in _ssots(example_plan, sel)["audio"]["data"]["music_themes"])


def test_dialogue_drama_keeps_vocal_title_song(example_plan):
    cues = _ssots(example_plan)["audio"]["data"]["cues"]
    assert [c for c in cues if c["type"] == "OST" and c["vocal"]]


def test_external_voice_can_route_to_typecast():
    cue = {"cue_id": "Q001", "type": "DIALOGUE", "tc_in": 0, "tc_out": 3, "description": "NAR: 안녕하세요", "vocal": True}
    [row] = sound.plan([cue], mood="m", era="e", external_voice=True, voice_provider="typecast")
    assert (row.provider, row.tool) == ("typecast", "typecast_tts")
    [default] = sound.plan([cue], mood="m", era="e", external_voice=True)
    assert default.provider == "fish_audio"


def test_execution_plan_accepts_typecast_dialogue_lane(tmp_path):
    assert main(["new", SAMPLE_REQUEST, "--projects-dir", str(tmp_path), "--project-id", "p", "--provider", "mock",
                 "--until", "G2_preproduction_review"]) == 0
    lane = {"kind": "dialogue", "provider": "typecast", "model": "ssfm-v30", "max_jobs": 8,
            "unit": "credits", "estimate": "100", "ceiling": "20000"}
    assert proposal(Project(tmp_path / "p"), {"lanes": [lane]})["lanes"]["dialogue"]["provider"] == "typecast"


def test_plan_review_recomputes_stale_preflight(tmp_path):
    assert main(["new", SAMPLE_REQUEST, "--projects-dir", str(tmp_path), "--project-id", "p", "--provider", "mock",
                 "--non-interactive", "--no-nonstop"]) == 0
    root = tmp_path / "p"
    plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    plan["preflight_checks"].append({"id": "P05", "item": "화자가 캐릭터 목록에 있음", "status": "fail", "detail": "stale"})
    (root / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    main(["run", str(root)])
    review = json.loads((root / "reviews/plan_review.json").read_text(encoding="utf-8"))
    assert review["status"] != "fail", review


def test_new_with_typecast_voice_routes_dialogue_cues(tmp_path):
    assert main(["new", SAMPLE_REQUEST, "--projects-dir", str(tmp_path), "--project-id", "p", "--provider", "mock",
                 "--non-interactive", "--voice-provider", "typecast"]) == 0
    root = tmp_path / "p"
    main(["accept", str(root), "plan"]); main(["run", str(root)])
    cues = json.loads((root / "assets/sound_plan.json").read_text(encoding="utf-8"))["cues"]
    dialogue = [c for c in cues if c["kind"] == "DIALOGUE"]
    assert dialogue and all(c["provider"] == "typecast" for c in dialogue)


def test_host_new_keeps_input_json_selection_after_intake(tmp_path):
    seed = {"format": "knowledge_short", "genre": ["sf"], "narrative": "mystery_payoff",
            "direction": {"texture": "cinematic", "expression": "live_action", "sound": "narration_driven"},
            "emotion_arc": ["curiosity"], "production_method": "live_action_ai"}
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps(seed), encoding="utf-8")
    assert main(["new", "우주에서 촛불을 켜면 생기는 일. 9:16 40초 지식 쇼츠", "--projects-dir", str(tmp_path),
                 "--project-id", "p", "--provider", "host", "--non-interactive", "--input-json", str(seed_path),
                 "--providers", "video=ludyte"]) == 0
    root = tmp_path / "p"
    answers = {k: {"noul": 0.1} for k in ("script", "scenario", "reference", "plot_concept", "lead_character", "voice", "direction")}
    (root / "agent_io/responses/intake_factors.json").write_text(json.dumps({"answers": answers}), encoding="utf-8")
    main(["run", str(root)])
    asked = sorted(p.stem for p in (root / "agent_io/requests").glob("recommend_*.json"))
    assert asked == [], asked
    sel = json.loads((root / "selection.json").read_text(encoding="utf-8"))
    assert sel["format"] == "knowledge_short" and sel["direction"]["sound"] == "narration_driven"
    assert sel["sources"]["format"] == "user"
