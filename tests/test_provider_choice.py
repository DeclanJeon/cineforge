import json

import pytest

from cineforge import agent_register, provider_registry as reg
from cineforge.cli import main
from cineforge.provider_choice import choose_interactive
from conftest import SAMPLE_REQUEST

INTAKE = {k: {"noul": 0.1} for k in ("script", "scenario", "reference", "plot_concept", "lead_character", "voice", "direction")}


def _inputs(root):
    return json.loads((root / "project.json").read_text(encoding="utf-8"))["inputs"]


# ---------- providers list / setup ----------

def test_providers_list_json_filters_lane(capsys):
    assert main(["services", "list", "--lane", "voice", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    ids = {r["id"] for r in rows}
    assert {"typecast", "elevenlabs", "native-audio"} <= ids and "runway" not in ids
    assert all("available" in r for r in rows)


def test_providers_setup_previews_without_yes_and_applies_with_yes(tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(agent_register, "detect", lambda home=None, which=None: ["pi", "codex"])
    monkeypatch.setattr(agent_register, "_run", lambda argv: (calls.append(argv), (0, "ok"))[1])
    monkeypatch.setattr("cineforge.mcp_discovery.discover", lambda home=None: [])
    assert main(["services", "setup", "pika"]) == 0
    out = capsys.readouterr().out
    assert "pi mcp add pika --url https://mcp.pika.art/mcp" in out and calls == []
    assert main(["services", "setup", "pika", "--yes"]) == 0
    out = capsys.readouterr().out
    assert [c[0] for c in calls] == ["pi", "codex"]
    assert "pi mcp login pika" in out


def test_providers_setup_rejects_unknown_provider(capsys):
    assert main(["services", "setup", "nope", "--yes"]) == 2


# ---------- per-project choice ----------

def test_new_with_providers_flag_records_choice_and_routes_voice(tmp_path):
    assert main(["new", SAMPLE_REQUEST, "--projects-dir", str(tmp_path), "--project-id", "p", "--provider", "mock",
                 "--non-interactive", "--providers", "video=runway,voice=typecast"]) == 0
    inputs = _inputs(tmp_path / "p")
    assert inputs["providers"]["video"] == "runway" and inputs["providers"]["voice"] == "typecast"
    assert inputs["voice_provider"] == "typecast" and inputs["external_voice"] is True
    assert inputs["providers_source"] == "flag"


def test_new_rejects_provider_outside_lane(tmp_path, capsys):
    assert main(["new", SAMPLE_REQUEST, "--projects-dir", str(tmp_path), "--project-id", "p", "--provider", "mock",
                 "--non-interactive", "--providers", "music=runway"]) == 2


def test_mock_run_without_choice_uses_defaults(tmp_path):
    assert main(["new", SAMPLE_REQUEST, "--projects-dir", str(tmp_path), "--project-id", "p", "--provider", "mock",
                 "--non-interactive"]) == 0
    inputs = _inputs(tmp_path / "p")
    assert inputs["providers"] == reg.defaults() and inputs["providers_source"] == "default"


def _host_project(tmp_path):
    assert main(["new", "우주에서 촛불을 켜면 생기는 일. 9:16 40초 지식 쇼츠", "--projects-dir", str(tmp_path),
                 "--project-id", "p", "--provider", "host", "--non-interactive"]) == 0
    root = tmp_path / "p"
    (root / "agent_io/responses/intake_factors.json").write_text(json.dumps({"answers": INTAKE}), encoding="utf-8")
    return root


def test_host_mode_emits_user_only_provider_choice_and_waits(tmp_path):
    root = _host_project(tmp_path)
    main(["run", str(root)])
    req = json.loads((root / "agent_io/requests/providers_choice.json").read_text(encoding="utf-8"))
    assert req["kind"] == "user_choice" and req["must_ask_user"] is True
    assert "사용자" in req["instructions"] and set(req["question"]["lanes"]) == set(reg.LANES)
    prog = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    assert prog["stages"]["S01_selection"]["status"] == "waiting_user"
    assert not list((root / "agent_io/requests").glob("recommend_*.json"))


def test_host_choice_answer_resumes_and_is_recorded(tmp_path):
    root = _host_project(tmp_path)
    main(["run", str(root)])
    answer = {"choices": {"video": "ludyte", "voice": "typecast", "music": "none"}, "user_said": "영상은 러다이트, 음성은 타입캐스트"}
    (root / "agent_io/responses/providers_choice.json").write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
    main(["run", str(root)])
    inputs = _inputs(root)
    assert inputs["providers"]["video"] == "ludyte" and inputs["providers"]["image"] == reg.defaults()["image"]
    assert inputs["providers_source"] == "user" and inputs["providers_user_said"].startswith("영상은")
    assert inputs["voice_provider"] == "typecast"
    assert list((root / "agent_io/requests").glob("recommend_*.json"))  # S01 continued


def test_host_choice_without_user_quote_is_rejected(tmp_path):
    root = _host_project(tmp_path)
    main(["run", str(root)])
    (root / "agent_io/responses/providers_choice.json").write_text(json.dumps({"choices": {"video": "ludyte"}}), encoding="utf-8")
    main(["run", str(root)])
    prog = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    assert prog["stages"]["S01_selection"]["status"] == "blocked"
    assert "user_said" in prog["stages"]["S01_selection"]["note"]


def test_interactive_choice_takes_numbers_enter_for_default():
    answers = iter(["2", "", "", "", "", ""])
    out = []
    picked = choose_interactive(ask=lambda prompt: next(answers), printer=out.append, available={"ludyte": True})
    video = reg.question(available={"ludyte": True})["lanes"]["video"]["options"]
    assert picked["video"] == video[1]["id"]
    assert picked["voice"] == reg.defaults()["voice"]
    assert any("영상 생성" in line for line in out)


def test_any_registered_voice_service_can_carry_dialogue(tmp_path):
    from cineforge import sound
    from cineforge.execution_plan import proposal
    from cineforge.pipeline import Project
    cue = {"cue_id": "Q001", "type": "DIALOGUE", "tc_in": 0, "tc_out": 3, "description": "N: 안녕", "vocal": True}
    [row] = sound.plan([cue], mood="m", era="e", external_voice=True, voice_provider="elevenlabs")
    assert (row.provider, row.tool) == ("elevenlabs", "elevenlabs_tts")
    assert main(["new", SAMPLE_REQUEST, "--projects-dir", str(tmp_path), "--project-id", "p", "--provider", "mock",
                 "--until", "G2_preproduction_review"]) == 0
    lane = {"kind": "dialogue", "provider": "cartesia", "model": "sonic", "max_jobs": 4, "unit": "credits", "estimate": "1", "ceiling": "10"}
    assert proposal(Project(tmp_path / "p"), {"lanes": [lane]})["lanes"]["dialogue"]["provider"] == "cartesia"
