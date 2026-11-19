"""오프라인 결정론적 판단 공급자(최종 폴백·테스트용).

질문의 hints만 사용한다.
- noul: hints.keywords 중 하나라도 state 텍스트에 있으면 1.0, hints.negative 가 있으면 0.0
- choice: hints.keywords[option] 매칭 수가 가장 큰 선택지, 없으면 hints.default 또는 첫 선택지
- score: hints.level(사전 계산 등급) 또는 hints.score(0~1) → 등급 매핑
"""
from __future__ import annotations

import json
from typing import Any

from cineforge.providers.base import Answer, DecisionProvider, Question


def _text(state: Any) -> str:
    if isinstance(state, str):
        return state
    return json.dumps(state, ensure_ascii=False)


class HeuristicDecisionProvider(DecisionProvider):
    name = "heuristic"

    def available(self) -> bool:
        return True

    def ask(self, state: Any, questions: list[Question]) -> dict[str, Answer]:
        text = _text(state).lower()
        out: dict[str, Answer] = {}
        for q in questions:
            hints = q.hints or {}
            if q.type == "noul":
                if any(neg.lower() in text for neg in hints.get("negative", [])):
                    value: Any = 0.0
                else:
                    value = 1.0 if any(k.lower() in text for k in hints.get("keywords", [])) else float(hints.get("default", 0.0))
                out[q.id] = Answer(q.id, "noul", value, 0.5, self.name)
            elif q.type == "choice":
                options = list(q.criteria or {})
                kw: dict[str, list[str]] = hints.get("keywords", {})
                scored = [(sum(text.count(k.lower()) for k in kw.get(o, [])), -i, o) for i, o in enumerate(options)]
                best = max(scored) if scored else (0, 0, None)
                value = best[2] if best[0] > 0 else hints.get("default", options[0] if options else None)
                out[q.id] = Answer(q.id, "choice", value, 0.5, self.name)
            else:
                levels = list(q.criteria or [])
                if "level" in hints and hints["level"] in levels:
                    value = hints["level"]
                else:
                    score = max(0.0, min(1.0, float(hints.get("score", 0.5))))
                    value = levels[min(len(levels) - 1, int(score * len(levels)))] if levels else score
                out[q.id] = Answer(q.id, "score", value, 0.5, self.name)
        return out
