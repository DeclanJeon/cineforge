"""Bare `cineforge`: pick the AI, make sure it is signed in, then open its agent session for production.

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
    "codex": {
        "label": "Codex (ChatGPT 계정으로 로그인)",
        "bin": "codex",
        "status": ["codex", "login", "status"],
        "login": ["codex", "login"],
        "install": "Codex CLI가 필요합니다. 설치: npm install -g @openai/codex (안내: https://developers.openai.com/codex/cli)",
    },
}
DEFAULT = "codex"

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
    quiet = argv[-1:] == ["status"]
    return subprocess.call(argv, stdout=subprocess.DEVNULL if quiet else None, stderr=subprocess.DEVNULL if quiet else None)


def _launch(argv: list[str], env: dict[str, str]) -> int:
    os.execvpe(argv[0], argv, env)
    return 0  # pragma: no cover - exec does not return


def _choose(ask: Callable[[str], str], printer: Callable[[str], None], last: str) -> str:
    ids = list(AGENTS)
    printer("\n어떤 AI로 진행할까요?")
    for n, key in enumerate(ids, start=1):
        printer(f"  {n}. {AGENTS[key]['label']} [{key}]")
    while True:
        raw = ask(f"선택 [{last}]: ").strip().lower()
        if not raw:
            return last
        if raw.isdigit() and 1 <= int(raw) <= len(ids):
            return ids[int(raw) - 1]
        if raw in AGENTS:
            return raw
        printer("목록의 번호나 이름을 입력하세요.")


def start(*, ask: Callable[[str], str] = input, printer: Callable[[str], None] = print,
          which: Callable[[str], str | None] = shutil.which, run: Callable[[list[str]], int] | None = None,
          launch: Callable[[list[str], dict[str, str]], int] | None = None, config: Path | None = None,
          env: dict[str, str] | None = None) -> int:
    run, launch = run or _run, launch or _launch
    env = dict(os.environ if env is None else env)
    config = config or config_path()
    try:
        last = json.loads(config.read_text(encoding="utf-8")).get("agent", DEFAULT)
    except (OSError, ValueError):
        last = DEFAULT
    if last not in AGENTS:
        last = DEFAULT
    printer("CineForge — 요구사항 한 번, 선택 한 번. 그다음은 논스톱.")
    key = _choose(ask, printer, last)
    agent = AGENTS[key]
    if not which(agent["bin"]):
        printer(agent["install"])
        return 1
    if run(agent["status"]) != 0:
        printer("로그인이 필요합니다. 브라우저에서 계정으로 로그인해 주세요.")
        run(agent["login"])
        if run(agent["status"]) != 0:
            printer("로그인을 확인하지 못했습니다. 다시 `cineforge`를 실행해 주세요.")
            return 1
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"agent": key}, ensure_ascii=False) + "\n", encoding="utf-8")
    env["CINEFORGE_AGENT_MODE"] = "1"
    prompt = PROMPT.format(cmd=env.get("CINEFORGE_CMD") or "cineforge")
    printer(f"{agent['label'].split(' (')[0]} 세션을 엽니다…")
    return int(launch([agent["bin"], prompt], env) or 0)
