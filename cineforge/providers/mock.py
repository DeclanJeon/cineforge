"""오프라인 목(mock) 생성 공급자 — 결정론적 템플릿 기획안. 실제 창작물이 아니라 구조 검증용 초안이다."""
from __future__ import annotations

from typing import Any

from cineforge.providers.base import GenerationProvider, ProviderError


class MockGenerationProvider(GenerationProvider):
    name = "mock"

    def available(self) -> bool:
        return True

    def generate(self, task: str, payload: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
        if task.startswith("plan"):
            from cineforge.planner import mock_plan  # 순환 import 방지
            return mock_plan(payload)
        raise ProviderError(f"mock 공급자는 '{task}' 작업을 지원하지 않습니다")
