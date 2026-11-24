"""Bare `cineforge`: pick the AI (pi with a chosen account, Codex, Claude Code or agy), make sure it is signed in, then open its session.

CineForge is driven by a coding agent. This launcher only chooses and starts that agent with
the working rules; it never stores credentials (sign-in is the agent CLI's own OAuth flow).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable

AGENTS: dict[str, dict[str, Any]] = {
    "pi": {
        "label": "pi (등록된 모든 프로바이더를 그대로 사용)",
        "bin": "pi",
        "install": "pi가 필요합니다. 설치: npm install -g @earendil-works/pi-coding-agent (안내: https://pi.dev)",
        # Offered only when pi has no usable provider yet; otherwise pi opens as the user already uses it.
        "accounts": [("openai-codex", "ChatGPT 계정"), ("anthropic", "Claude 계정"), ("github-copilot", "GitHub Copilot 계정")],
    },
    "codex": {
        "label": "Codex (ChatGPT 계정으로 로그인)",
        "bin": "codex",
        "status": ["codex", "login", "status"],
        "login": ["codex", "login"],
        "install": "Codex CLI가 필요합니다. 설치: npm install -g @openai/codex (안내: https://developers.openai.com/codex/cli)",
    },
    "claude": {
        "label": "Claude Code (Claude 계정으로 로그인)",
        "bin": "claude",
        "status": ["claude", "auth", "status"],   # exits 0 when signed in, 1 otherwise
        "login": ["claude", "auth", "login"],
        "rules": "system",                         # --append-system-prompt, then an opening message
        "install": "Claude Code가 필요합니다. 설치 안내: https://code.claude.com/docs/en/setup",
    },
    "agy": {
        "label": "agy · Antigravity CLI (Google 계정으로 로그인)",
        "bin": "agy",
        # No status command: agy opens Google Sign-In itself when no session is stored.
        "note": "로그인이 안 돼 있으면 agy가 시작하면서 Google 로그인 창을 엽니다.",
        "rules": "interactive",                    # agy -i "<rules + opening>"
        "install": "Antigravity CLI(agy)가 필요합니다. 설치: curl -fsSL https://antigravity.google/cli/install.sh | bash "
                   "(안내: https://antigravity.google/docs/cli/reference)",
    },
}
DEFAULT = "pi"
OPENING = "CineForge 제작을 시작합니다. 먼저 어떤 영상을 만들지 물어봐 주세요."

PROMPT = """당신은 CineForge 영상 제작 진행자입니다. 사용자와 대화하며 아래 규칙으로 제작을 진행하세요.

1. 먼저 사용자에게 어떤 영상을 만들지 물어보세요(이미 말했다면 생략).
2. 요청을 받으면 원문 그대로 `{cmd} new "<요청 원문>" --projects-dir ./productions --project-id <영문-소문자-하이픈>`을 실행합니다.
3. 이후 `{cmd} run <프로젝트 경로>`를 반복합니다. `agent_io/requests/<이름>.json`에 응답이 필요하다고 나오면 내용을 읽고 `agent_io/responses/<이름>.json`에 답을 쓴 뒤 다시 run 합니다.
4. 요청의 kind가 `user_choice`(must_ask_user)이면 절대 대신 답하지 마세요. 용도별로 이미 등록된 서비스(available=true)와 기본값을 먼저 보여 주고, 원하면 전체 목록도 보여 준 뒤, 사용자가 고른 것만 choices에, 사용자가 실제로 한 말을 user_said에 적습니다.
5. 사용자가 등록되지 않은 서비스를 고르면 `{cmd} services setup <id>`로 미리보기를 보여 주고, 동의하면 `--yes`를 붙여 등록한 뒤 로그인 방법을 안내합니다.
6. 비용이 드는 생성, 승인(accept·grant·verify), 게시는 사용자가 확인하기 전에는 하지 않습니다. 실패하거나 불확실한 작업을 자동으로 다시 시도하지 않습니다.
7. 진행 상황은 `{cmd} status <프로젝트 경로>`로 확인해 짧게 알려 줍니다.
8. cineforge-production 스킬이 설치되어 있으면 그 지침을 함께 따릅니다.
"""


def config_path() -> Path:
    return Path.home() / ".config/cineforge/agent.json"


def _run(argv: list[str]) -> int:
    quiet = argv[-1:] == ["status"] or "check" in argv[:3]
    return subprocess.call(argv, stdout=subprocess.DEVNULL if quiet else None, stderr=subprocess.DEVNULL if quiet else None)


def _launch(argv: list[str], env: dict[str, str]) -> int:
    os.execvpe(argv[0], argv, env)
    return 0  # pragma: no cover - exec does not return


def _capture(argv: list[str]) -> str:
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def pi_providers(capture: Callable[[list[str]], str]) -> dict[str, int]:
    """Providers pi can use right now (built-in sign-ins, API keys and custom ones), with model counts."""
    counts: dict[str, int] = {}
    for line in capture(["pi", "--list-models"]).splitlines()[1:]:
        cells = line.split()
        if len(cells) >= 2:
            counts[cells[0]] = counts.get(cells[0], 0) + 1
    return counts


def _choose(ask: Callable[[str], str], printer: Callable[[str], None], last: str, installed: set[str]) -> str:
    ids = list(AGENTS)
    printer("\n어떤 AI로 진행할까요? (✓ = 이 PC에 설치됨)")
    for n, key in enumerate(ids, start=1):
        printer(f"  {n}. {'✓' if key in installed else ' '} {AGENTS[key]['label']} [{key}]")
    while True:
        raw = ask(f"선택 [{last}]: ").strip().lower()
        if not raw:
            return last
        if raw.isdigit() and 1 <= int(raw) <= len(ids):
            return ids[int(raw) - 1]
        if raw in AGENTS:
            return raw
        printer("목록의 번호나 이름을 입력하세요.")


def _pi_sign_in(agent: dict[str, Any], ask: Callable[[str], str], printer: Callable[[str], None],
                run: Callable[[list[str]], int], capture: Callable[[list[str]], str]) -> bool:
    """pi has no usable provider yet: sign in to one account in the browser."""
    accounts = agent["accounts"]
    ids = [acc for acc, _ in accounts]
    printer("\npi에 등록된 프로바이더가 없습니다. 어떤 계정으로 로그인할까요?")
    for n, (acc, label) in enumerate(accounts, start=1):
        printer(f"  {n}. {label} [{acc}]")
    while True:
        raw = ask(f"선택 [{ids[0]}]: ").strip().lower()
        if not raw:
            chosen = ids[0]
        elif raw.isdigit() and 1 <= int(raw) <= len(ids):
            chosen = ids[int(raw) - 1]
        elif raw in ids:
            chosen = raw
        else:
            printer("목록의 번호나 이름을 입력하세요.")
            continue
        break
    run(["pi", "auth", "login", chosen])
    if not pi_providers(capture):
        printer("로그인을 확인하지 못했습니다. 다시 `cineforge`를 실행해 주세요.")
        return False
    return True


def start(*, ask: Callable[[str], str] = input, printer: Callable[[str], None] = print,
          which: Callable[[str], str | None] = shutil.which, run: Callable[[list[str]], int] | None = None,
          launch: Callable[[list[str], dict[str, str]], int] | None = None, config: Path | None = None,
          env: dict[str, str] | None = None, capture: Callable[[list[str]], str] | None = None) -> int:
    run, launch, capture = run or _run, launch or _launch, capture or _capture
    env = dict(os.environ if env is None else env)
    config = config or config_path()
    try:
        saved = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    installed = {key for key, spec in AGENTS.items() if which(spec["bin"])}
    last = saved.get("agent") or next((key for key in AGENTS if key in installed), DEFAULT)
    if last not in AGENTS:
        last = DEFAULT
    printer("CineForge — 요구사항 한 번, 선택 한 번. 그다음은 논스톱.")
    key = _choose(ask, printer, last, installed)
    agent = AGENTS[key]
    if not which(agent["bin"]):
        printer(agent["install"])
        return 1
    remember: dict[str, str] = {"agent": key}
    prompt = PROMPT.format(cmd=env.get("CINEFORGE_CMD") or "cineforge")
    if "accounts" in agent:
        providers = pi_providers(capture)
        if not providers and not _pi_sign_in(agent, ask, printer, run, capture):
            return 1
        providers = providers or pi_providers(capture)
        printer("pi에 등록된 프로바이더: " + ", ".join(f"{name}({count})" for name, count in sorted(providers.items()))
                + " — 세션 안에서 /model로 바꿀 수 있습니다.")
        # pi opens exactly as the user already uses it (its own default model, every provider available).
        # Rules go in the system prompt so they survive long sessions; the opening message makes the agent ask first.
        argv = [agent["bin"], "--append-system-prompt", prompt, OPENING]
    else:
        if agent.get("status") and run(agent["status"]) != 0:
            printer("로그인이 필요합니다. 브라우저에서 계정으로 로그인해 주세요.")
            run(agent["login"])
            if run(agent["status"]) != 0:
                printer("로그인을 확인하지 못했습니다. 다시 `cineforge`를 실행해 주세요.")
                return 1
        if agent.get("note"):
            printer(agent["note"])
        rules = agent.get("rules")
        if rules == "system":
            argv = [agent["bin"], "--append-system-prompt", prompt, OPENING]
        elif rules == "interactive":
            argv = [agent["bin"], "-i", f"{prompt}\n{OPENING}"]
        else:
            argv = [agent["bin"], prompt]
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(remember, ensure_ascii=False) + "\n", encoding="utf-8")
    env["CINEFORGE_AGENT_MODE"] = "1"
    printer(f"{agent['label'].split(' (')[0]} 세션을 엽니다…")
    return int(launch(argv, env) or 0)
