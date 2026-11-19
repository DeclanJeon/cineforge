"""호스트 에이전트 공급자(에이전트 인 더 루프).

CineForge를 실행한 AI 에이전트(Claude Code/Codex/Grok Bot 등)가 자신의 모델로 판단·생성한다.
1) 요청 파일 agent_io/requests/<task>.json 을 쓴다(프롬프트·입력·스키마·응답 경로 포함).
2) 응답 파일 agent_io/responses/<task>.json 이 없으면 AgentInputRequired 를 던진다.
3) 에이전트가 응답을 쓰고 `cineforge run <project>` 를 다시 실행하면 이어서 진행한다.
API 키가 필요 없고, 유료 호출도 없다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from cineforge.providers.base import (AgentInputRequired, Answer, DecisionProvider, GenerationProvider,
                                      ProviderError, Question, parse_jev_answers)

SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _slug(task: str) -> str:
    return SAFE.sub("_", task)[:80]


class _HostIO:
    def __init__(self, io_dir: Path) -> None:
        self.io_dir = Path(io_dir)
        self.requests = self.io_dir / "requests"
        self.responses = self.io_dir / "responses"

    def exchange(self, task: str, request: dict[str, Any]) -> dict[str, Any]:
        slug = _slug(task)
        req = self.requests / f"{slug}.json"
        res = self.responses / f"{slug}.json"
        if res.is_file():
            try:
                return json.loads(res.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ProviderError(f"에이전트 응답 JSON 오류: {res} ({exc.msg})") from None
        self.requests.mkdir(parents=True, exist_ok=True)
        self.responses.mkdir(parents=True, exist_ok=True)
        request = dict(request, response_path=str(res))
        req.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
        raise AgentInputRequired(req, res, task)


class HostAgentDecisionProvider(DecisionProvider):
    name = "host-agent"

    def __init__(self, io_dir: Path) -> None:
        self.io = _HostIO(io_dir)
        self._counter = 0

    def available(self) -> bool:
        return True

    def ask(self, state: Any, questions: list[Question], task: str | None = None) -> dict[str, Answer]:
        task = task or "decision_" + "_".join(q.id for q in questions)[:60]
        request = {
            "kind": "decision",
            "instructions": ("각 질문에 System One 형식으로 답하세요. 응답은 {\"answers\": {질문id: {...}}} JSON. "
                             "noul → {\"noul\": 0~1}, choice → {\"choice\": 선택지키}, score → {\"score\": 등급문자열}."),
            "state": state,
            "questions": {q.id: q.to_wire() for q in questions},
        }
        raw = self.io.exchange(task, request)
        return parse_jev_answers(raw, questions, self.name)


class HostAgentGenerationProvider(GenerationProvider):
    name = "host-agent"

    def __init__(self, io_dir: Path) -> None:
        self.io = _HostIO(io_dir)

    def available(self) -> bool:
        return True

    def generate(self, task: str, payload: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
        request = {
            "kind": "generation",
            "instructions": ("input을 바탕으로 schema를 만족하는 JSON을 응답 파일에 쓰세요. 한국어로 작성하고, "
                             "선택된 콘셉트·연출 규칙·제약(constraints)을 모두 지키세요. 실존 작품의 대사·캐릭터를 복제하지 마세요."),
            "task": task,
            "input": payload,
            "schema": schema,
        }
        return self.io.exchange(task, request)
