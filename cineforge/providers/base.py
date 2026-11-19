"""공급자 공통 타입.

판단(Decision)은 Jev(System One)의 질문 타입을 그대로 따른다.
- noul: 예/아니오 확률(0~1)
- choice: 정해진 선택지 중 하나
- score: 순서 있는 등급 중 하나
생성(Generation)은 JSON 스키마를 만족하는 구조화 결과를 돌려준다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

QuestionType = Literal["noul", "choice", "score"]


class ProviderError(RuntimeError):
    """공급자 호출 실패(다음 공급자로 폴백)."""


class ProviderUnavailable(ProviderError):
    """키 없음·네트워크 차단 등으로 사용할 수 없음."""


class AgentInputRequired(Exception):
    """호스트 에이전트가 응답 파일을 채워야 계속할 수 있음(에이전트 인 더 루프)."""

    def __init__(self, request_path: Path, response_path: Path, task: str) -> None:
        super().__init__(f"에이전트 응답 필요: {task} → {response_path}")
        self.request_path = request_path
        self.response_path = response_path
        self.task = task


@dataclass
class Question:
    id: str
    type: QuestionType
    instructions: str
    criteria: Any = None  # choice: {option: desc}, score: [level, ...], noul: str|None
    hints: dict[str, Any] = field(default_factory=dict)  # 오프라인 휴리스틱 전용(외부로 전송하지 않음)

    def to_wire(self) -> dict[str, Any]:
        wire: dict[str, Any] = {"type": self.type, "instructions": self.instructions}
        if self.criteria is not None:
            wire["criteria"] = self.criteria
        return wire


@dataclass
class Answer:
    id: str
    type: QuestionType
    value: Any  # noul: float, choice: str, score: str(level)
    confidence: float | None = None
    provider: str = ""
    probabilities: dict[str, float] | None = None

    @property
    def yes(self) -> bool:
        return self.type == "noul" and float(self.value) >= 0.5

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "value": self.value, "confidence": self.confidence,
                "provider": self.provider}


class DecisionProvider:
    name = "base"

    def available(self) -> bool:  # pragma: no cover - interface
        return False

    def ask(self, state: Any, questions: list[Question]) -> dict[str, Answer]:  # pragma: no cover
        raise NotImplementedError


class GenerationProvider:
    name = "base"

    def available(self) -> bool:  # pragma: no cover - interface
        return False

    def generate(self, task: str, payload: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError  # pragma: no cover


def parse_jev_answers(raw: dict[str, Any], questions: list[Question], provider: str) -> dict[str, Answer]:
    """TypeSafe System One 응답(answers 맵)을 Answer로 변환. 형태가 다르면 ProviderError."""
    answers = raw.get("answers", raw)
    if not isinstance(answers, dict):
        raise ProviderError("answers 형식이 아닙니다")
    result: dict[str, Answer] = {}
    for q in questions:
        entry = answers.get(q.id)
        if not isinstance(entry, dict):
            raise ProviderError(f"질문 {q.id}의 응답이 없습니다")
        if q.type == "noul":
            value: Any = float(entry.get("noul", entry.get("value", 0.0)))
        elif q.type == "choice":
            value = entry.get("choice", entry.get("value"))
            if isinstance(q.criteria, dict) and value not in q.criteria:
                raise ProviderError(f"질문 {q.id}: 선택지 밖의 답 {value!r}")
        else:
            value = entry.get("score", entry.get("value"))
            if isinstance(q.criteria, list) and value not in q.criteria:
                # 숫자 인덱스로 돌아오는 경우
                if isinstance(value, int) and 0 <= value < len(q.criteria):
                    value = q.criteria[value]
                else:
                    raise ProviderError(f"질문 {q.id}: 등급 밖의 답 {value!r}")
        result[q.id] = Answer(q.id, q.type, value, entry.get("confidence"), provider, entry.get("probabilities"))
    return result
