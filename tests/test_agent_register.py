import json
from pathlib import Path

from cineforge import agent_register as ar
from cineforge import mcp_discovery, provider_registry as reg


def _home(tmp_path):
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    (home / ".codex/config.toml").write_text('[mcp_servers.Ludyte]\nurl = "https://mcp.ludyte.com/mcp"\n', encoding="utf-8")
    (home / ".gemini").mkdir()
    (home / ".gemini/settings.json").write_text(json.dumps({"security": {"auth": "x"}}), encoding="utf-8")
    (home / ".config/opencode").mkdir(parents=True)
    (home / ".config/opencode/opencode.jsonc").write_text(
        '{\n  // comment\n  "mcp": {\n    "runway": {"type": "remote", "url": "https://mcp.runwayml.com/mcp"}\n  }\n}\n', encoding="utf-8")
    return home


def _which(*present):
    return lambda name: f"/usr/bin/{name}" if name in present else None


def test_discovery_reads_opencode_jsonc_and_gemini_http_url(tmp_path):
    home = _home(tmp_path)
    (home / ".gemini/settings.json").write_text(json.dumps({"mcpServers": {"pika": {"httpUrl": "https://mcp.pika.art/mcp"}}}), encoding="utf-8")
    rows = {(r["agent"], r["name"]): r for r in mcp_discovery.discover(home)}
    assert rows[("opencode", "runway")]["url"] == "https://mcp.runwayml.com/mcp"
    assert rows[("gemini", "pika")]["url"] == "https://mcp.pika.art/mcp"


def test_detect_counts_cli_on_path_or_gemini_settings(tmp_path):
    home = _home(tmp_path)
    assert ar.detect(home, _which("pi", "codex", "opencode")) == ["pi", "codex", "opencode", "gemini"]
    assert "claude" in ar.detect(home, _which("claude"))


def test_plan_adds_where_missing_and_skips_existing_by_name_or_url(tmp_path):
    home = _home(tmp_path)
    agents = ar.detect(home, _which("pi", "codex", "opencode"))
    steps = {s.agent: s for s in ar.plan(reg.get("ludyte"), agents, mcp_discovery.discover(home))}
    assert steps["codex"].action == "skip"
    assert steps["pi"].argv == ["pi", "mcp", "add", "ludyte", "--url", "https://mcp.ludyte.com/mcp"]
    assert steps["opencode"].argv == ["opencode", "mcp", "add", "ludyte", "--global", "--url", "https://mcp.ludyte.com/mcp"]
    assert steps["gemini"].action == "add" and steps["gemini"].file.endswith(".gemini/settings.json")
    runway = {s.agent: s for s in ar.plan(reg.get("runway"), agents, mcp_discovery.discover(home))}
    assert runway["opencode"].action == "skip"


def test_api_key_provider_registers_env_var_reference_never_a_secret(tmp_path):
    home = _home(tmp_path)
    fal = reg.get("fal")
    steps = {s.agent: s for s in ar.plan(fal, ["pi", "codex", "opencode", "claude"], [])}
    var = fal["env_var"]
    assert steps["codex"].argv[-2:] == ["--bearer-token-env-var", var]
    assert steps["pi"].argv[-2:] == ["--bearer-token-env-var", var]
    assert f"{{env:{var}}}" in " ".join(steps["opencode"].argv)
    assert f"${{{var}}}" in " ".join(steps["claude"].argv)


def test_local_cli_and_builtin_providers_are_manual_or_skipped():
    assert {s.action for s in ar.plan(reg.get("minimax"), ["pi", "codex"], [])} == {"manual"}
    assert {s.action for s in ar.plan(reg.get("typecast"), ["pi"], [])} == {"manual"}
    assert {s.action for s in ar.plan(reg.get("native-audio"), ["pi"], [])} == {"skip"}


def test_apply_runs_commands_and_edits_gemini_with_backup(tmp_path):
    home = _home(tmp_path)
    calls = []

    def run(argv):
        calls.append(argv)
        return 0, "ok"

    steps = ar.plan(reg.get("pika"), ["pi", "codex", "gemini"], mcp_discovery.discover(home))
    results = ar.apply(steps, run=run, home=home)
    assert [c[0] for c in calls] == ["pi", "codex"]
    assert all(r["ok"] for r in results)
    settings = json.loads((home / ".gemini/settings.json").read_text(encoding="utf-8"))
    assert settings["mcpServers"]["pika"] == {"httpUrl": "https://mcp.pika.art/mcp"}
    assert settings["security"] == {"auth": "x"}
    assert (home / ".gemini/settings.json.cineforge.bak").is_file()


def test_apply_reports_command_failure_without_stopping_others(tmp_path):
    home = _home(tmp_path)
    steps = ar.plan(reg.get("pika"), ["pi", "codex"], [])
    results = ar.apply(steps, run=lambda argv: (1, "boom") if argv[0] == "pi" else (0, "ok"), home=home)
    assert [(r["agent"], r["ok"]) for r in results] == [("pi", False), ("codex", True)]


def test_login_hints_cover_each_registered_agent():
    hints = ar.login_hints(reg.get("pika"), ["pi", "codex", "opencode", "gemini", "claude"])
    assert "pi mcp login pika" in hints["pi"] and "codex mcp login pika" in hints["codex"]
    assert set(hints) == {"pi", "codex", "opencode", "gemini", "claude"}


def test_runner_stops_at_success_line_instead_of_waiting_for_oauth(tmp_path):
    script = tmp_path / "fake-codex"
    script.write_text("#!/bin/sh\necho \"Added global MCP server 'pika'.\"\necho 'Starting OAuth flow'\nsleep 30\n", encoding="utf-8")
    script.chmod(0o755)
    import time
    start = time.monotonic()
    code, out = ar._stream_run([str(script)], success_marker="Added global MCP server", timeout=20)
    assert code == 0 and "Added global MCP server" in out
    assert time.monotonic() - start < 5
    assert "codex mcp login" in ar.login_hints({"id": "pika", "auth": "oauth"}, ["codex"])["codex"]
