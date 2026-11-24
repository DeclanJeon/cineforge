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
        self.prompts = getattr(self, "prompts", []) + [prompt]
        return next(self.answers, "")

    def out_prompts(self):
        return getattr(self, "prompts", [])

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
                              capture=lambda argv: "", config=tmp_path / "agent.json", env={"PATH": "/usr/bin"}, **kw)


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


# ---------- pi: the user's existing pi, with every provider already registered ----------

LIST = """provider      model            context  max-out  thinking  images
anthropic     claude-opus-5    1M       128K     yes       yes
anthropic     claude-haiku-5   1M       128K     yes       yes
openai-codex  gpt-6.1-sol      1M       128K     yes       yes
openrouter    openrouter/auto  2M       64K      yes       yes
my-gateway    local-model      32K      8K       no        no
"""


class PiRecorder(Recorder):
    def __init__(self, answers=(), listing=LIST, login_ok=True, pi=True):
        super().__init__(answers=answers)
        self.listing, self.login_ok, self.pi = listing, login_ok, pi

    def which(self, name):
        return f"/usr/bin/{name}" if (name == "pi" and self.pi) else None

    def capture(self, argv):
        self.calls.append(argv)
        return self.listing if argv == ["pi", "--list-models"] else ""

    def run(self, argv):
        self.calls.append(argv)
        if argv[:3] == ["pi", "auth", "login"]:
            if self.login_ok:
                self.listing = LIST
            return 0 if self.login_ok else 1
        return 0

    def start(self, tmp_path, **kw):
        return launcher.start(ask=self.ask, printer=self.out.append, which=self.which, run=self.run, launch=self.launch,
                              capture=self.capture, config=tmp_path / "agent.json", env={"PATH": "/usr/bin"}, **kw)


def test_pi_opens_as_is_with_every_registered_provider(tmp_path):
    r = PiRecorder(answers=[""])                      # Enter = pi (default); no account question follows
    assert r.start(tmp_path) == 0
    text = "\n".join(r.out)
    for provider in ("anthropic", "openai-codex", "openrouter", "my-gateway"):   # custom providers too
        assert provider in text
    argv, env = r.launched
    assert argv[0] == "pi" and "--models" not in argv and "--model" not in argv and "--provider" not in argv
    assert "user_choice" in argv[argv.index("--append-system-prompt") + 1]
    assert "영상" in argv[-1] and env["CINEFORGE_AGENT_MODE"] == "1"
    assert len(r.out_prompts()) == 1                  # only the AI question was asked
    assert not [c for c in r.calls if c[:3] == ["pi", "auth", "login"]]
    assert json.loads((tmp_path / "agent.json").read_text(encoding="utf-8")) == {"agent": "pi"}


def test_pi_without_any_provider_offers_sign_in_then_opens(tmp_path):
    r = PiRecorder(answers=["pi", "2"], listing="provider  model\n")
    assert r.start(tmp_path) == 0
    assert ["pi", "auth", "login", "anthropic"] in r.calls
    assert "--models" not in r.launched[0]


def test_pi_stops_when_sign_in_fails_and_explains_missing_pi(tmp_path):
    r = PiRecorder(answers=["pi", "1"], listing="", login_ok=False)
    assert r.start(tmp_path) == 1 and r.launched is None
    r2 = PiRecorder(answers=["pi"], pi=False)
    assert r2.start(tmp_path) == 1 and "pi" in "\n".join(r2.out) and r2.launched is None


def test_menu_marks_installed_agents_and_defaults_to_an_installed_one(tmp_path):
    r = Recorder(answers=[""])                        # only codex is installed in this recorder
    assert r.start(tmp_path) == 0
    assert any(line.strip().startswith("2. ✓") and "[codex]" in line for line in r.out)
    assert any(line.strip().startswith("1.") and "[pi]" in line and "✓" not in line for line in r.out)
    assert r.launched[0][0] == "codex"


# ---------- Claude Code and agy (Antigravity CLI) ----------

class CliRecorder(Recorder):
    """Any agent CLI: `bins` on PATH, `signed_in` per binary, `login_ok` for the browser sign-in."""

    def __init__(self, answers=(), bins=("claude", "agy"), signed_in=("claude",), login_ok=True):
        super().__init__(answers=answers)
        self.bins, self.signed_in, self.login_ok = set(bins), set(signed_in), login_ok

    def which(self, name):
        return f"/usr/bin/{name}" if name in self.bins else None

    def run(self, argv):
        self.calls.append(argv)
        if argv[1:] == ["auth", "status"]:
            return 0 if argv[0] in self.signed_in else 1
        if argv[1:] == ["auth", "login"]:
            if self.login_ok:
                self.signed_in.add(argv[0])
            return 0 if self.login_ok else 1
        return 0


def test_menu_offers_pi_codex_claude_and_agy(tmp_path):
    r = CliRecorder(answers=["claude"])
    r.start(tmp_path)
    text = "\n".join(r.out)
    for name in ("[pi]", "[codex]", "[claude]", "[agy]"):
        assert name in text


def test_claude_code_opens_with_rules_in_system_prompt(tmp_path):
    r = CliRecorder(answers=["claude"])
    assert r.start(tmp_path) == 0
    argv, env = r.launched
    assert argv[0] == "claude" and "user_choice" in argv[argv.index("--append-system-prompt") + 1]
    assert "영상" in argv[-1] and env["CINEFORGE_AGENT_MODE"] == "1"
    assert ["claude", "auth", "login"] not in r.calls
    assert json.loads((tmp_path / "agent.json").read_text(encoding="utf-8"))["agent"] == "claude"


def test_claude_code_signs_in_when_needed_and_stops_on_failure(tmp_path):
    r = CliRecorder(answers=["claude"], signed_in=())
    assert r.start(tmp_path) == 0
    assert r.calls[:3] == [["claude", "auth", "status"], ["claude", "auth", "login"], ["claude", "auth", "status"]]
    bad = CliRecorder(answers=["claude"], signed_in=(), login_ok=False)
    assert bad.start(tmp_path) == 1 and bad.launched is None


def test_agy_opens_interactive_prompt_and_leaves_sign_in_to_agy(tmp_path):
    r = CliRecorder(answers=["agy"])
    assert r.start(tmp_path) == 0
    argv, env = r.launched
    assert argv[:2] == ["agy", "-i"] and len(argv) == 3
    assert "user_choice" in argv[2] and "cineforge new" in argv[2] and "영상" in argv[2]
    assert env["CINEFORGE_AGENT_MODE"] == "1"
    assert r.calls == []                                   # agy has no status command; it signs in on start
    assert "Google" in "\n".join(r.out)


def test_missing_claude_or_agy_explains_install(tmp_path):
    for key, needle in (("claude", "code.claude.com"), ("agy", "antigravity.google/cli/install.sh")):
        r = CliRecorder(answers=[key], bins=())
        assert r.start(tmp_path) == 1 and r.launched is None
        assert needle in "\n".join(r.out)


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
