# ADR-009 OpenRouter 경유 Jev는 Decisions API로 부른다

- 상황: ADR-004는 OpenRouter chat/completions로 System One 질문 맵을 보내는 실험 형식이었다. 2026-11-19 실호출 결과 chat/completions는 400("typesafe/jev-1.14 is a decisions model and cannot be used with the chat/completions endpoint")으로 거부됐다.
- 결정: `JevOpenRouterDecisionProvider`는 `POST https://openrouter.ai/api/alpha/decisions`에 `{model: "typesafe/jev-1.14", state, questions}`를 보낸다. 같은 본문을 `POST /api/v1/systemone`(TypeSafe 호환 경로)에 보내도 같은 응답이 온다.
- 응답 처리: `answers[id].type`을 먼저 본다. `refusal`·누락·예상 밖 유형은 '아니오'가 아니라 '답 없음'으로 보고 폴백한다(fail closed). score는 0..N-1 연속값과 버킷 확률로 오므로 최빈 버킷(없으면 반올림)을 등급으로 쓴다. `usage.cost`는 `last_usage`에 남긴다.
- 실측: 질문 3개(noul·choice·score), 입력 452토큰, 출력 78토큰, 비용 $0.000019, 응답 약 0.3초. 모델 `typesafe/jev-1.14-20261014`, 공급자 TypeSafe.
- 검증: `tests/test_providers.py`(가짜 transport로 요청·응답 형태 고정), `tests/test_live_openrouter.py::test_live_jev_decisions`(opt-in 실호출).
