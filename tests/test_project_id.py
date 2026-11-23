from pathlib import Path

import pytest

from cineforge.cli import main
from cineforge.pipeline import Project
from cineforge.route import judge


REQUEST = "좋아 콘텐츠 제작 스킬과 CineForge를 소개하는 영상 만들어줘"


@pytest.mark.parametrize("project_id", [None, "", "한글", "Uppercase", "two words", "../escape", "-leading", "trailing-"])
def test_create_requires_ascii_project_id(tmp_path: Path, project_id: str | None) -> None:
    with pytest.raises(ValueError, match="프로젝트명"):
        Project.create(tmp_path / "productions", REQUEST, "mock", project_id)
    assert not (tmp_path / "productions").exists()


def test_cli_without_id_requires_input_when_piped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                  capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["new", REQUEST, "--projects-dir", str(tmp_path), "--provider", "mock"]) == 2
    assert "--project-id" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("argv", [[], ["--non-interactive"]])
def test_cli_tty_prompts_for_id_only_when_interactive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                      argv: list[str]) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    prompts: list[str] = []

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        return "cineforge-demo-2"

    monkeypatch.setattr("builtins.input", answer)
    result = main(["new", REQUEST, "--projects-dir", str(tmp_path), "--provider", "mock", "--until", "S03_plan", *argv])
    if argv:
        assert result == 2
        assert not prompts
        assert not list(tmp_path.iterdir())
    else:
        assert result == 0
        assert len(prompts) == 1 and "프로젝트명" in prompts[0]
        project = Project(tmp_path / "cineforge-demo-2")
        assert project.meta["request"] == REQUEST
        assert project.meta["project_id"] == project.progress()["project_id"] == "cineforge-demo-2"
        assert project.read("plan.json")["title"] != "cineforge-demo-2"


def test_cli_reports_invalid_explicit_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["new", REQUEST, "--projects-dir", str(tmp_path), "--project-id", "한글", "--provider", "mock"]) == 2
    assert "--project-id" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("request_text", [REQUEST, "서버 소개 영상 만들어줘"])
def test_route_tells_host_to_supply_project_id(request_text: str) -> None:
    hint = judge(request_text)["next"]
    assert isinstance(hint, str)
    assert '--project-id' in hint
    assert '요구사항' in hint
