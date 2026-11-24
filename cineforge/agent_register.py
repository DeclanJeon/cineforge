"""Register one provider's MCP server in every installed agent, only on an explicit `providers setup`.

Each agent's own CLI is preferred; only Gemini (no add command assumed) gets a JSON edit,
with a backup first. Secrets are never written: API-key servers reference an environment
variable name. OAuth sign-in stays a per-agent browser step (see login_hints).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable
from urllib.parse import urlsplit

ORDER = ("pi", "codex", "opencode", "claude", "gemini")
GEMINI_SETTINGS = ".gemini/settings.json"


@dataclass(frozen=True, slots=True)
class Step:
    agent: str
    action: str  # add | skip | manual
    reason: str
    argv: list[str] | None = None
    file: str | None = None
    entry: dict[str, Any] = field(default_factory=dict)
    name: str = ""


def _norm(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _url_key(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    return (parts.netloc.lower() + parts.path.rstrip("/")).lower()


def detect(home: Path | None = None, which: Callable[[str], str | None] = shutil.which) -> list[str]:
    """Agents present on this machine: CLI on PATH, or Gemini's settings file."""
    base = home or Path.home()
    found = []
    for agent in ORDER:
        if which(agent) or (agent == "gemini" and (base / GEMINI_SETTINGS).is_file()):
            found.append(agent)
    return found


def _existing(rows: list[dict[str, Any]], agent: str, provider: dict[str, Any]) -> str | None:
    names = {_norm(provider["id"]), _norm(provider["name"])}
    target = _url_key(provider.get("url"))
    for row in rows:
        if row.get("agent") != agent:
            continue
        if _norm(row.get("name", "")) in names or (target and _url_key(row.get("url")) == target):
            return str(row.get("name"))
    return None


def _add_argv(agent: str, name: str, url: str, env_var: str | None, which: Callable[[str], str | None]) -> tuple[list[str] | None, dict[str, Any]]:
    if agent == "pi":
        return ["pi", "mcp", "add", name, "--url", url] + (["--bearer-token-env-var", env_var] if env_var else []), {}
    if agent == "codex":
        return ["codex", "mcp", "add", name, "--url", url] + (["--bearer-token-env-var", env_var] if env_var else []), {}
    if agent == "opencode":
        return ["opencode", "mcp", "add", name, "--global", "--url", url] + (["--header", f"Authorization=Bearer {{env:{env_var}}}"] if env_var else []), {}
    if agent == "claude":
        return ["claude", "mcp", "add", "--transport", "http", "-s", "user", name, url] + (["--header", f"Authorization: Bearer ${{{env_var}}}"] if env_var else []), {}
    if agent == "gemini":
        entry: dict[str, Any] = {"httpUrl": url}
        if env_var:
            entry["headers"] = {"Authorization": f"Bearer ${env_var}"}
        if which("gemini"):
            argv = ["gemini", "mcp", "add", "--transport", "http", "-s", "user", name, url]
            return argv + (["--header", f"Authorization: Bearer ${env_var}"] if env_var else []), entry
        return None, entry
    raise ValueError(f"unknown_agent: {agent}")


def plan(provider: dict[str, Any], agents: list[str], existing: list[dict[str, Any]],
         *, which: Callable[[str], str | None] = lambda name: None) -> list[Step]:
    name = provider["id"]
    steps: list[Step] = []
    for agent in agents:
        transport = provider["transport"]
        if transport in ("builtin", "none"):
            steps.append(Step(agent, "skip", "CineForge 내장 또는 사용 안 함 — 등록할 서버 없음", name=name))
            continue
        if transport in ("local", "cli"):
            how = " ".join(provider.get("command") or []) or provider.get("docs", "")
            steps.append(Step(agent, "manual", f"로컬 설치·로그인 필요: {how} (안내: {provider.get('docs', '')})", name=name))
            continue
        found = _existing(existing, agent, provider)
        if found:
            steps.append(Step(agent, "skip", f"이미 등록됨: {found}", name=name))
            continue
        env_var = provider.get("env_var") if provider["auth"] == "api_key" else None
        argv, entry = _add_argv(agent, name, provider["url"], env_var, which)
        if argv:
            steps.append(Step(agent, "add", "에이전트 CLI로 등록", argv=argv, name=name))
        else:
            steps.append(Step(agent, "add", "설정 파일에 추가(백업 후)", file=GEMINI_SETTINGS, entry=entry, name=name))
    return steps


def _run(argv: list[str]) -> tuple[int, str]:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _edit_gemini(home: Path, name: str, entry: dict[str, Any]) -> str:
    path = home / GEMINI_SETTINGS
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if path.is_file():
        shutil.copy2(path, path.with_name(path.name + ".cineforge.bak"))
    data.setdefault("mcpServers", {})[name] = entry
    tmp = path.with_name(path.name + ".cineforge.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return str(path)


def apply(steps: list[Step], *, run: Callable[[list[str]], tuple[int, str]] | None = None, home: Path | None = None) -> list[dict[str, Any]]:
    run = run or _run  # resolved at call time so tests and callers can replace the module runner
    base = home or Path.home()
    results = []
    for step in steps:
        if step.action != "add":
            results.append({"agent": step.agent, "action": step.action, "ok": True, "detail": step.reason})
            continue
        try:
            if step.argv:
                code, out = run(step.argv)
                results.append({"agent": step.agent, "action": "add", "ok": code == 0, "detail": out[-400:]})
            else:
                results.append({"agent": step.agent, "action": "add", "ok": True, "detail": _edit_gemini(base, step.name, step.entry)})
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            results.append({"agent": step.agent, "action": "add", "ok": False, "detail": str(exc)})
    return results


def login_hints(provider: dict[str, Any], agents: list[str]) -> dict[str, str]:
    name = provider["id"]
    if provider["auth"] == "api_key":
        key = f"환경변수 {provider.get('env_var')}에 API 키를 넣으세요({provider.get('docs', '')}). "
    else:
        key = ""
    hints = {"pi": f"{key}pi mcp login {name}", "codex": f"{key}codex mcp login {name}",
             "opencode": f"{key}opencode에서 /mcp 또는 opencode mcp auth {name}",
             "claude": f"{key}Claude Code에서 /mcp → {name} 선택 후 브라우저 로그인",
             "gemini": f"{key}Gemini CLI에서 /mcp auth {name}"}
    return {agent: hints[agent] for agent in agents}
