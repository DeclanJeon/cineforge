"""원격 공급자: Jev 1.14(OpenRouter Decisions API 또는 TypeSafe 직접) 판단 + OpenRouter 생성.

- OpenRouter 경유 Jev는 chat/completions가 아니라 Decisions API(POST /api/alpha/decisions)로 부른다.
  2026-11-19 실호출로 확인(ADR-009). chat/completions로 보내면 400("decisions model").

- 키는 환경변수에서만 읽는다(OPENROUTER_API_KEY, TYPESAFE_API_KEY). 파일·로그·인자에 남기지 않는다.
- 네트워크 호출은 transport 함수로 주입 가능(테스트는 가짜 transport 사용, 실제 호출 없음).
- 어떤 실패든 ProviderError/ProviderUnavailable로 바꿔 상위 라우터가 다음 공급자로 폴백하게 한다.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

from cineforge.providers.base import (Answer, DecisionProvider, GenerationProvider, ProviderError,
                                      ProviderUnavailable, Question, parse_jev_answers)

Transport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"  # 호환 경로: /api/v1/systemone
TYPESAFE_BASE = "https://api.typesafe.ai/v1"
JEV_OPENROUTER_SLUG = "typesafe/jev-1.14"          # 2026-11-19 확인: openrouter.ai/typesafe/jev-1.14
JEV_OPENROUTER_PINNED = "typesafe/jev-1.14-20261014"
JEV_TYPESAFE_MODEL = "jev-1.14.0"
# 기획안·문장 생성 기본 모델(ADR-008). CINEFORGE_GEN_MODEL로 덮어쓰고, "off"/"none"이면 끈다.
DEFAULT_GEN_MODEL = "openai/gpt-6.1-terra"
GEN_MODEL_DISABLED = {"off", "none", "0", "false", ""}


def urllib_transport(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 고정 https URL
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # 상태 + 오류 메시지만 노출(요청 헤더·키는 담지 않음)
        detail = ""
        try:
            detail = str(json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", ""))[:200]
        except Exception:  # noqa: BLE001 - 오류 본문은 참고용
            pass
        raise ProviderError(f"HTTP {exc.code}" + (f": {detail}" if detail else "")) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderUnavailable(f"네트워크 오류: {type(exc).__name__}") from None
    except json.JSONDecodeError:
        raise ProviderError("JSON이 아닌 응답") from None


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


class JevTypeSafeDecisionProvider(DecisionProvider):
    """TypeSafe System One API 직접 호출(문서화된 정식 형태)."""

    name = "jev-typesafe"

    def __init__(self, model: str = JEV_TYPESAFE_MODEL, transport: Transport | None = None,
                 env: dict[str, str] | None = None, timeout: float = 30.0) -> None:
        self.model, self.transport, self.timeout = model, transport or urllib_transport, timeout
        self.env = env if env is not None else os.environ

    def available(self) -> bool:
        return bool(self.env.get("TYPESAFE_API_KEY"))

    def ask(self, state: Any, questions: list[Question]) -> dict[str, Answer]:
        key = self.env.get("TYPESAFE_API_KEY")
        if not key:
            raise ProviderUnavailable("TYPESAFE_API_KEY 없음")
        body = {"model": self.model, "state": state, "questions": {q.id: q.to_wire() for q in questions}}
        raw = self.transport(f"{TYPESAFE_BASE}/systemone",
                             {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                             body, self.timeout)
        return parse_jev_answers(raw, questions, self.name)


class JevOpenRouterDecisionProvider(DecisionProvider):
    """OpenRouter Decisions API 경유 Jev 1.14.

    요청: POST https://openrouter.ai/api/alpha/decisions
          {"model": "typesafe/jev-1.14", "state": <문자열|객체>, "questions": {id: {type, instructions, criteria}}}
    응답: {"model", "provider", "id", "answers": {id: {type, choice|noul|score, probabilities, confidence}},
           "usage": {"input_tokens", "output_tokens", "cost"}}
    마지막 호출의 usage는 last_usage에 남긴다(비용 추적). 실패하면 ProviderError → 다음 공급자로 폴백.
    """

    name = "jev-openrouter"

    def __init__(self, model: str = JEV_OPENROUTER_SLUG, transport: Transport | None = None,
                 env: dict[str, str] | None = None, timeout: float = 30.0) -> None:
        self.model, self.transport, self.timeout = model, transport or urllib_transport, timeout
        self.env = env if env is not None else os.environ
        self.last_usage: dict[str, Any] | None = None

    def available(self) -> bool:
        return bool(self.env.get("OPENROUTER_API_KEY"))

    def ask(self, state: Any, questions: list[Question]) -> dict[str, Answer]:
        key = self.env.get("OPENROUTER_API_KEY")
        if not key:
            raise ProviderUnavailable("OPENROUTER_API_KEY 없음")
        body = {"model": self.model, "state": state, "questions": {q.id: q.to_wire() for q in questions}}
        raw = self.transport(OPENROUTER_DECISIONS_URL,
                             {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                              "X-Title": "CineForge"}, body, self.timeout)
        if not isinstance(raw, dict) or not isinstance(raw.get("answers"), dict):
            raise ProviderError("OpenRouter Decisions 응답에 answers가 없습니다")
        self.last_usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else None
        return parse_jev_answers(raw, questions, self.name)


class OpenRouterGenerationProvider(GenerationProvider):
    """OpenRouter의 일반 생성 모델(문장·기획안 생성). Jev는 생성용이 아니므로 별도 모델을 쓴다.

    기본 모델은 DEFAULT_GEN_MODEL(ADR-008). CINEFORGE_GEN_MODEL로 덮어쓰고 "off"면 끈다.
    유료 호출의 opt-in은 OPENROUTER_API_KEY 설정 자체다(키가 없으면 절대 호출하지 않음).
    """

    name = "openrouter-gen"

    def __init__(self, model: str | None = None, transport: Transport | None = None,
                 env: dict[str, str] | None = None, timeout: float = 120.0) -> None:
        self.env = env if env is not None else os.environ
        configured = model if model is not None else self.env.get("CINEFORGE_GEN_MODEL")
        if configured is None:
            self.model: str | None = DEFAULT_GEN_MODEL
        elif configured.strip().lower() in GEN_MODEL_DISABLED:
            self.model = None
        else:
            self.model = configured.strip()
        self.transport, self.timeout = transport or urllib_transport, timeout
        self.last_usage: dict[str, Any] | None = None

    def available(self) -> bool:
        return bool(self.env.get("OPENROUTER_API_KEY") and self.model)

    def generate(self, task: str, payload: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
        key = self.env.get("OPENROUTER_API_KEY")
        if not key or not self.model:
            raise ProviderUnavailable("OPENROUTER_API_KEY 없음 또는 생성 모델 꺼짐(CINEFORGE_GEN_MODEL=off)")
        system = ("너는 한국어 영상 기획 작가다. 요청 JSON을 읽고, 주어진 JSON 스키마를 만족하는 JSON 하나만 출력한다. "
                  "설명 문장이나 코드펜스 없이 JSON만.")
        user = json.dumps({"task": task, "input": payload, "schema": schema}, ensure_ascii=False)
        body = {"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"}, "usage": {"include": True}}
        raw = self.transport(f"{OPENROUTER_BASE}/chat/completions",
                             {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "CineForge"},
                             body, self.timeout)
        self.last_usage = raw.get("usage") if isinstance(raw, dict) and isinstance(raw.get("usage"), dict) else None
        try:
            return json.loads(_strip_fences(raw["choices"][0]["message"]["content"]))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ProviderError("생성 응답이 JSON이 아닙니다") from None
