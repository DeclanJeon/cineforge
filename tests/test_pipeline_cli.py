import json
from pathlib import Path

import pytest

from cineforge.cli import main
from cineforge.data_loader import load
from cineforge.pipeline import Project
from cineforge.progress import rates
from conftest import ROOT, SAMPLE_REQUEST


def _status(root):
    return {k: v["status"] for k, v in json.loads((Path(root) / "progress.json").read_text(encoding="utf-8"))["stages"].items()}


def test_mock_pipeline_gates_and_authority(tmp_path, capsys):
    assert main(["new", SAMPLE_REQUEST, "--projects-dir", str(tmp_path), "--project-id", "p", "--provider", "mock", "--non-interactive", "--no-nonstop"]) == 0
    root = tmp_path / "p"
    st = _status(root)
    assert st["S03_plan"] == "done" and st["G1_plan_review"] == "waiting_user"
    for f in ("intake.json", "selection.json", "concept.json", "plan.json", "plan.md"):
        assert (root / f).is_file(), f
    assert main(["accept", str(root), "plan"]) == 0
    assert main(["run", str(root)]) == 0
    st = _status(root)
    assert st["S07_assets"] == "done" and st["G2_preproduction_review"] == "waiting_user"
    for f in ("frames", "image_prompts", "video_prompts", "sound_cue_sheet", "asset_registry"):
        assert (root / "assets" / f"{f}.json").is_file()
    assert len(list((root / "ssot").glob("*.json"))) == 8
    main(["accept", str(root), "preproduction"])
    main(["run", str(root)])
    st = _status(root)
    assert st["S08_generation"] == "blocked"  # 실행 권한 없이는 생성 단계 차단
    handoff = json.loads((root / "handoffs/S08_generation.json").read_text(encoding="utf-8"))
    assert handoff["authority_required"] == "execution" and handoff["authority_granted"] is False
    main(["grant", str(root), "execution", "--spend-ceiling", "20USD"])
    main(["run", str(root)])
    assert _status(root)["S08_generation"] == "waiting_external"
    handoff = json.loads((root / "handoffs/S08_generation.json").read_text(encoding="utf-8"))
    assert handoff["authority_granted"] is True and handoff["packet"]["spend_ceiling"] == "20USD"
    # 증거 없이는 완료 불가
    assert main(["complete", str(root), "S08_generation"]) == 1
    ev = root / "renders.txt"
    ev.write_text("cut01.mp4\n", encoding="utf-8")
    assert main(["complete", str(root), "S08_generation", "--evidence", str(ev)]) == 0
    assert _status(root)["S08_generation"] == "done"
    capsys.readouterr()


def test_nonstop_reaches_generation_handoff(tmp_path, capsys):
    main(["new", SAMPLE_REQUEST, "--projects-dir", str(tmp_path), "--project-id", "n", "--provider", "mock",
          "--non-interactive", "--nonstop"])
    st = _status(tmp_path / "n")
    assert st["G2_preproduction_review"] == "done" and st["S08_generation"] == "blocked"
    out = capsys.readouterr().out
    assert "진행률" in out and "작업률" in out and "조합된 제작 콘셉트" in out


def test_progress_rates_monotonic(tmp_path):
    project = Project.create(tmp_path, SAMPLE_REQUEST, "mock", "r")
    pipeline = load("pipeline.yaml")
    before = rates(project.progress(), pipeline)
    project.run(until="S03_plan")
    after = rates(project.progress(), pipeline)
    assert after[0] > before[0] and after[1] > before[1]
    assert 0 <= after[0] <= 100 and 0 <= after[1] <= 100


def test_host_mode_with_example_plan(tmp_path, example_plan):
    project = Project.create(tmp_path, SAMPLE_REQUEST, "host", "h")
    io = tmp_path / "h" / "agent_io"
    for _ in range(30):
        prog = project.run()
        pending = [p for p in sorted((io / "requests").glob("*.json")) if not (io / "responses" / p.name).exists()]
        if not pending:
            break
        for req_path in pending:
            req = json.loads(req_path.read_text(encoding="utf-8"))
            if req["kind"] == "decision":
                ans = {}
                for qid, q in req["questions"].items():
                    if q["type"] == "noul":
                        ans[qid] = {"noul": 0.5}
                    elif q["type"] == "choice":
                        keys = list(q["criteria"])
                        pick = next((k for k in ("laughter", "dialogue_driven", "r9_16") if k in keys), keys[0])
                        ans[qid] = {"choice": pick}
                    else:
                        ans[qid] = {"score": q["criteria"][-2]}
                out = {"answers": ans}
            else:
                out = example_plan
            (io / "responses").mkdir(parents=True, exist_ok=True)
            (io / "responses" / req_path.name).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        project = Project(tmp_path / "h")
    plan = json.loads((tmp_path / "h/plan.json").read_text(encoding="utf-8"))
    assert plan["title"] == "《면접관이 제 전 여친입니다》"
    assert prog["stages"]["G1_plan_review"]["status"] == "waiting_user"
    project.accept("plan")
    prog = project.run()
    review = json.loads((tmp_path / "h/reviews/preproduction_review.json").read_text(encoding="utf-8"))
    assert review["status"] in ("pass", "warn"), review["issues"]


def test_impact_marks_stages_stale(tmp_path):
    project = Project.create(tmp_path, SAMPLE_REQUEST, "mock", "i")
    project.grant(accept_plan=True)
    project.run(until="S07_assets")
    stages = project.apply_impact("character")
    assert "S05_character_world" in stages
    st = project.progress()["stages"]
    assert st["S05_character_world"]["status"] == "stale"
    assert st["S04_story"]["status"] == "done"


def test_cli_taxonomy_export_matches_skill_copy(tmp_path, capsys):
    target = tmp_path / "concept-taxonomy.yaml"
    assert main(["taxonomy", "--export", str(target), "--with-rules"]) == 0
    assert target.read_bytes() == (ROOT / "cineforge/data/taxonomy.yaml").read_bytes()
    assert (tmp_path / "concept-rules.yaml").is_file()
    skill_copy = ROOT.parents[1] / "04_Skills/Skills-and-Automation/contents-production-skills/concept-intake-design/references/concept-taxonomy.yaml"
    if skill_copy.exists():
        assert skill_copy.read_bytes() == target.read_bytes(), "스킬 저장소의 taxonomy 사본이 동기화되지 않음"
    capsys.readouterr()


def test_cli_lists_and_providers(capsys):
    assert main(["taxonomy", "--axis", "narrative"]) == 0
    out = capsys.readouterr().out
    assert "결말 선공개형" in out
    assert main(["providers"]) == 0
    desc = json.loads(capsys.readouterr().out)
    assert desc["mode"] == "auto"


def test_cli_rejects_bad_set(tmp_path, capsys):
    rc = main(["new", "x", "--projects-dir", str(tmp_path), "--project-id", "b", "--provider", "mock", "--non-interactive",
               "--set", "narrative=없는구조"])
    assert rc == 1
    capsys.readouterr()


def test_no_secret_in_project_files(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret-xyz")

    def boom(*_a, **_k):
        raise OSError("network disabled in tests")

    import cineforge.providers.remote as remote
    monkeypatch.setattr(remote, "urllib_transport", boom)
    main(["new", SAMPLE_REQUEST, "--projects-dir", str(tmp_path), "--project-id", "s", "--provider", "mock", "--non-interactive"])
    for f in (tmp_path / "s").rglob("*"):
        if f.is_file():
            assert "sk-or-secret-xyz" not in f.read_text(encoding="utf-8", errors="ignore"), f
    capsys.readouterr()
