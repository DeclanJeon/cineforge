import hashlib
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


def make_skill_pack(root: Path, label: str = "fixture") -> Path:
    from cineforge.data_loader import load

    stages = {}
    skills = set()
    files = {}
    for sid, stage in load("legacy_skill_routes.yaml").items():
        owners = stage["skills"]
        skills.update(owners)
        row = {"route": stage.get("route"), "owners": owners, "refs": []}
        if sid in {"S06_storyboard", "S07_assets", "S08_generation", "S09_edit", "S10_qa"}:
            row["when"] = {
                "cut_revision": {"refs": ["video-production-assets/references/21-generated-video-qa-retry.md"]},
                "code_motion": {"refs": ["creative-production/references/motion-pipeline.md",
                                         "video-production-assets/references/08b-code-motion-production.md",
                                         "video-production-assets/assets/code-motion-brief-template.md"]},
                "realtime_3d": {"refs": ["open-3d-production/references/realtime-motion-direction.md"]},
            }
            for bundle in row["when"].values():
                files.update({p: label for p in bundle["refs"]})
        stages[sid] = row
    skills.update(name.split('/')[0] for name in files)
    files.update({f"{name}/SKILL.md": label for name in skills})
    guide = f"storyboarding-video/{label}.md"
    files[guide] = label
    stages["S06_storyboard"]["refs"] = [] if label == "fixture" else [guide]
    inv = "integrations/cineforge/files.json"
    for relative, value in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    (root / inv).parent.mkdir(parents=True, exist_ok=True)
    (root / inv).write_text(json.dumps({
        p: hashlib.sha256(value.encode()).hexdigest() for p, value in files.items()
    }), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({
        "name": "contents-production-skills", "version": label, "skills": sorted(skills),
        "integrations": {"cineforge": {"contract_version": 1, "stages": stages,
                                       "delivery_files": ["storyboarding-video/SKILL.md"], "inventory": inv}},
    }), encoding="utf-8")
    return root


@pytest.fixture(scope="session")
def fixture_pack(tmp_path_factory):
    return make_skill_pack(tmp_path_factory.mktemp("skill-pack"))


@pytest.fixture(autouse=True)
def _isolated_skill_store(monkeypatch, tmp_path_factory):
    """The real user's skill-pack store and active pointer are never read in tests."""
    base = tmp_path_factory.mktemp("xdg")
    monkeypatch.setenv("XDG_DATA_HOME", str(base / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(base / "config"))


@pytest.fixture(autouse=True)
def _fixture_pack_env(monkeypatch, fixture_pack):
    monkeypatch.setenv("CINEFORGE_SKILL_PACK", str(fixture_pack))


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


@pytest.fixture(autouse=True)
def _never_touch_real_agents(monkeypatch, tmp_path):
    """Agent registration must never run real `pi/codex/... mcp add` or edit real configs in tests."""
    from cineforge import agent_register

    def refuse(argv):
        raise AssertionError(f"test tried to run a real agent command: {argv}")

    monkeypatch.setattr(agent_register, "_run", refuse)
    real_edit = agent_register._edit_gemini

    def guarded_edit(home, name, entry):
        if Path(home).resolve() == Path.home().resolve():
            raise AssertionError("test tried to edit the real ~/.gemini/settings.json")
        return real_edit(home, name, entry)

    monkeypatch.setattr(agent_register, "_edit_gemini", guarded_edit)


@pytest.fixture(autouse=True)
def _outside_any_agent(monkeypatch):
    """Tests often run inside a coding agent; agent auto-detection must not leak into them."""
    from cineforge.providers.router import AGENT_ENV

    for name in (*AGENT_ENV, "CINEFORGE_AGENT_MODE"):
        monkeypatch.delenv(name, raising=False)
