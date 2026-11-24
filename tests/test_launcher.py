import json

import pytest

from cineforge import launcher
from cineforge.cli import main
from cineforge.providers.host_agent import HostAgentDecisionProvider
from cineforge.providers.router import build_router, in_agent_context

INTAKE = {k: {"noul": 0.1} for k in ("script", "scenario", "reference", "plot_concept", "lead_character", "voice", "direction")}


# ---------- agent context auto-detection ----------

@pytest.mark.parametrize("env,expected", [
    ({}, False),
    ({"PI_CODING_AGENT": "1"}, True),
    ({"CLAUDECODE": "1"}, True),
    ({"CODEX_THREAD_ID": "abc"}, True),
    ({"CINEFORGE_AGENT_MODE": "1"}, True),
    ({"PI_CODING_AGENT": "1", "CINEFORGE_AGENT_MODE": "0"}, False),
])
def test_agent_context_detection(env, expected):
    assert in_agent_context(env) is expected


def test_auto_mode_routes_to_host_agent_inside_an_agent(tmp_path):
    inside = build_router("auto", io_dir=tmp_path, env={"PI_CODING_AGENT": "1"})
    outside = build_router("auto", io_dir=tmp_path, env={})
    assert inside.agent and any(isinstance(p, HostAgentDecisionProvider) for p in inside.decision_chain)
    assert not outside.agent and not any(isinstance(p, HostAgentDecisionProvider) for p in outside.decision_chain)
    assert build_router("host", io_dir=tmp_path, env={}).agent
    assert not build_router("mock", io_dir=tmp_path, env={"PI_CODING_AGENT": "1"}).agent


def test_default_provider_inside_agent_hands_service_choice_to_user(tmp_path, monkeypatch):
    monkeypatch.setenv("PI_CODING_AGENT", "1")
    assert main(["new", "고양이가 처음 눈을 보는 순간 20초 쇼츠", "--projects-dir", str(tmp_path), "--project-id", "p",
                 "--non-interactive"]) == 0
    root = tmp_path / "p"
    (root / "agent_io/responses/intake_factors.json").write_text(json.dumps({"answers": INTAKE}), encoding="utf-8")
    main(["run", str(root)])
    req = json.loads((root / "agent_io/requests/providers_choice.json").read_text(encoding="utf-8"))
    assert req["kind"] == "user_choice"


# ---------- bare `cineforge` launcher ----------

class Recorder:
    def __init__(self, answers=(), logged_in=True, login_ok=True, codex=True):
        self.answers, self.out, self.calls = iter(answers), [], []
        self.logged_in, self.login_ok, self.codex, self.launched = logged_in, login_ok, codex, None

    def ask(self, prompt):
        self.out.append(prompt)
        return next(self.answers, "")

    def which(self, name):
        return f"/usr/bin/{name}" if (name == "codex" and self.codex) else None

    def run(self, argv):
        self.calls.append(argv)
        if argv[:3] == ["codex", "login", "status"]:
            return 0 if self.logged_in else 1
        if argv[:2] == ["codex", "login"]:
            self.logged_in = self.login_ok
            return 0 if self.login_ok else 1
        return 0

    def launch(self, argv, env):
        self.launched = (argv, env)
        return 0

    def start(self, tmp_path, **kw):
        return launcher.start(ask=self.ask, printer=self.out.append, which=self.which, run=self.run, launch=self.launch,
                              config=tmp_path / "agent.json", env={"PATH": "/usr/bin"}, **kw)


def test_launcher_asks_ai_first_then_opens_codex_in_agent_mode(tmp_path):
    r = Recorder(answers=["codex"])
    assert r.start(tmp_path) == 0
    assert "어떤 AI" in "\n".join(r.out) and "Codex" in "\n".join(r.out)
    argv, env = r.launched
    assert argv[0] == "codex" and len(argv) == 2
    assert env["CINEFORGE_AGENT_MODE"] == "1"
    prompt = argv[1]
    for needle in ("cineforge new", "user_choice", "사용자", "cineforge services setup"):
        assert needle in prompt
    assert ["codex", "login"] not in r.calls


def test_launcher_runs_oauth_login_when_not_signed_in(tmp_path):
    r = Recorder(answers=["codex"], logged_in=False)
    assert r.start(tmp_path) == 0
    assert r.calls[:3] == [["codex", "login", "status"], ["codex", "login"], ["codex", "login", "status"]]
    assert r.launched is not None


def test_launcher_stops_when_login_fails(tmp_path):
    r = Recorder(answers=["codex"], logged_in=False, login_ok=False)
    assert r.start(tmp_path) == 1
    assert r.launched is None and "로그인" in "\n".join(r.out)


def test_launcher_explains_missing_codex(tmp_path):
    r = Recorder(answers=["codex"], codex=False)
    assert r.start(tmp_path) == 1
    assert r.launched is None and "Codex CLI" in "\n".join(r.out)


def test_launcher_remembers_last_choice_and_rejects_unknown(tmp_path):
    r = Recorder(answers=["9", "codex"])
    assert r.start(tmp_path) == 0
    assert json.loads((tmp_path / "agent.json").read_text(encoding="utf-8"))["agent"] == "codex"
    assert any("목록" in line for line in r.out)


def test_launcher_tells_agent_which_cineforge_command_to_run(tmp_path):
    r = Recorder(answers=["codex"])
    launcher.start(ask=r.ask, printer=r.out.append, which=r.which, run=r.run, launch=r.launch,
                   config=tmp_path / "agent.json", env={"PATH": "/usr/bin", "CINEFORGE_CMD": "/opt/dev/cineforge"})
    assert "/opt/dev/cineforge new" in r.launched[0][1]


# ---------- pi: one agent, several AI accounts ----------

class PiRecorder(Recorder):
    def __init__(self, answers=(), ready=("openai-codex",), login_ok=True, pi=True):
        super().__init__(answers=answers)
        self.ready, self.login_ok, self.pi = set(ready), login_ok, pi

    def which(self, name):
        return f"/usr/bin/{name}" if (name == "pi" and self.pi) else None

    def run(self, argv):
        self.calls.append(argv)
        if argv[:3] == ["pi", "auth", "check"]:
            return 0 if argv[argv.index("--provider") + 1] in self.ready else 1
        if argv[:3] == ["pi", "auth", "login"]:
            if self.login_ok:
                self.ready.add(argv[3])
            return 0 if self.login_ok else 1
        return 0


def test_pi_is_the_default_ai_and_lists_accounts_with_readiness(tmp_path):
    r = PiRecorder(answers=["", ""], ready=("anthropic",))
    assert r.start(tmp_path) == 0
    text = "\n".join(r.out)
    assert "pi" in text and "ChatGPT" in text and "Claude" in text and "GitHub Copilot" in text
    assert any(line.strip().startswith("2. ✓") and "Claude" in line for line in r.out)
    argv, env = r.launched
    assert argv[0] == "pi" and argv[argv.index("--models") + 1] == "anthropic/*"   # Enter = the signed-in account
    assert env["CINEFORGE_AGENT_MODE"] == "1"
    rules = argv[argv.index("--append-system-prompt") + 1]
    assert "user_choice" in rules and "cineforge new" in rules
    assert "영상" in argv[-1] and not argv[-1].startswith("-")                     # opening message makes the agent ask first
    assert not [c for c in r.calls if c[:3] == ["pi", "auth", "login"]]


def test_pi_signs_in_through_browser_when_chosen_account_is_not_ready(tmp_path):
    r = PiRecorder(answers=["pi", "anthropic"], ready=("openai-codex",))
    assert r.start(tmp_path) == 0
    assert ["pi", "auth", "login", "anthropic"] in r.calls
    assert r.launched[0][r.launched[0].index("--models") + 1] == "anthropic/*"
    assert json.loads((tmp_path / "agent.json").read_text(encoding="utf-8")) == {"agent": "pi", "account": "anthropic"}


def test_pi_stops_when_sign_in_fails_and_explains_missing_pi(tmp_path):
    r = PiRecorder(answers=["pi", "3"], ready=(), login_ok=False)
    assert r.start(tmp_path) == 1 and r.launched is None
    r2 = PiRecorder(answers=["pi"], pi=False)
    assert r2.start(tmp_path) == 1 and "pi" in "\n".join(r2.out) and r2.launched is None


def test_pi_remembers_last_account_as_default(tmp_path):
    (tmp_path / "agent.json").write_text(json.dumps({"agent": "pi", "account": "anthropic"}), encoding="utf-8")
    r = PiRecorder(answers=["", ""], ready=("openai-codex", "anthropic"))
    assert r.start(tmp_path) == 0
    assert r.launched[0][r.launched[0].index("--models") + 1] == "anthropic/*"


def test_bare_command_without_terminal_prints_usage(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_bare_command_in_terminal_starts_launcher(monkeypatch):
    seen = []
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(launcher, "start", lambda **kw: seen.append(1) or 0)
    assert main([]) == 0 and seen == [1]
