# 10. LLM 공급자 라우팅 — Jev 1.14 조사와 폴백

## 1. 조사 결과(2026-11-19)

| 항목 | 내용 |
|---|---|
| OpenRouter 모델 | `typesafe/jev-1.14` (고정 버전 `typesafe/jev-1.14-20261014`), 별칭 `typesafe/jev-router`, `~typesafe/jev-latest` |
| 정체 | TypeSafe의 "System One" 구조화 판단 모델, 2026-10-14 공개 |
| 가격 | 입력 100만 토큰당 $0.042, 출력 무료(조사 시점) |
| 컨텍스트 | OpenRouter 표기 262K. TypeSafe 직접 API는 요청당 64k / 질문당 32k |
| 출력 | 산문이 아닌 typed 답: Choice `{choice, probabilities, confidence}`, Score `{score, legend, probabilities, confidence}`, Noul `{noul: 0~1}`, Box(이미지 영역) |
| 직접 API | `POST https://api.typesafe.ai/v1/systemone`, `{model: "jev-1.14.0", state, questions: {id: {type, instructions, criteria}}}` → `{answers: {id: {...}}}`. 별칭 `jev-latest` |
| OpenRouter 요청(실호출 확인) | `POST https://openrouter.ai/api/alpha/decisions` (호환 경로 `POST /api/v1/systemone`도 같은 응답), 헤더 `Authorization: Bearer $OPENROUTER_API_KEY`, 본문 `{model: "typesafe/jev-1.14", state: 문자열|객체, questions: {id: {type, instructions, criteria}}}` |
| OpenRouter 응답 | `{model: "typesafe/jev-1.14-20261014", provider: "TypeSafe", id: "gen-dec-…", answers: {id: {type, choice|noul|score, legend, probabilities, confidence}}, usage: {input_tokens, output_tokens, cost}}`. score는 0..N-1 연속값(예 1.71) + 버킷 확률 → 최빈 버킷을 등급으로 씀 |
| 안 되는 것 | `/api/v1/chat/completions`로 보내면 400 "decisions model and cannot be used with the chat/completions endpoint". 모델 목록 `/api/v1/models` 기본값에는 텍스트 모델만 나오므로 `?output_modalities=decisions`로 조회 |

결론: Jev는 **판단 전용**(요소 판정·추천·채점)으로 쓰고, 기획안 같은 문장 생성은 호스트 AI 또는 별도 생성 모델이 맡는다(ADR-003). OpenRouter 경유 Jev는 Decisions API로 부르며(ADR-009, ADR-004 대체), 실패·거부(`type: refusal`)면 폴백한다.

## 2. 체인

| 모드 | 판단 체인 | 생성 체인 |
|---|---|---|
| auto(기본) | jev-openrouter → jev-typesafe → (CINEFORGE_AGENT_MODE=1이면) host-agent → heuristic | openrouter-gen → (agent mode) host-agent → mock |
| host | jev-openrouter → jev-typesafe → host-agent | host-agent |
| openrouter | jev-openrouter → jev-typesafe → heuristic | openrouter-gen |
| mock | heuristic | mock |

- 공급자는 키가 있을 때만 `available`. 키: `OPENROUTER_API_KEY`, `TYPESAFE_API_KEY`(환경변수만).
- 생성 모델 기본값은 `openai/gpt-6.2-sol`(ADR-010, 사용자 지정 "6.2 sol", 입력 $2/M·출력 $10/M). `CINEFORGE_GEN_MODEL`로 덮어쓰고 `off`면 끈다. 유료 호출의 opt-in은 `OPENROUTER_API_KEY` 설정 자체이며 키가 없으면 절대 호출하지 않는다.
- 어떤 오류든 `ProviderError`로 바뀌고 라우터가 다음 공급자로 넘어가며 `provider_log.json`에 `fallback`과 이유를 남긴다. 키 값은 로그·파일에 남지 않는다(테스트로 확인).
- 호스트 대기(`AgentInputRequired`)는 폴백하지 않고 단계를 `waiting_agent`로 만든다.

## 3. 질문 형식

```python
Question(id="recommend_narrative", type="choice", instructions="…가장 어울리는 항목은?",
         criteria={"ending_first": "결말 선공개형", "twist": "반전형", …},
         hints={"default": "twist"})   # hints는 오프라인 규칙 전용, 외부로 보내지 않음
```

| 쓰임 | 유형 | 개수 |
|---|---|---|
| 9개 판단 요소 판정 | noul | 7(콘텐츠 콘셉트·스토리 전개는 축 감지로 판정) |
| 축 추천 | choice | 열린 축마다 1 |
| 콘셉트 평가 | score(10/30/50/70/90) | 6 × (본안 + 대안 2) |

## 4. 호스트 에이전트 프로토콜

- 요청: `agent_io/requests/<task>.json` — `{kind: decision|generation, instructions, state 또는 input, questions 또는 schema, response_path}`.
- 응답: `agent_io/responses/<task>.json` — 판단은 `{answers: {...}}`(System One과 같은 모양), 생성은 스키마를 만족하는 JSON(예: plan.schema.json).
- 응답이 스키마·선택지 밖이면 `ProviderError` → 단계 `failed`, 응답을 고쳐 `run`.
- 이 프로토콜 덕분에 Claude Code·Codex 같은 호스트 에이전트가 스킬을 읽고 같은 질문에 답할 수 있다.

## 5. 비용 메모

Jev 판단 1회(질문 1~9개, 상태 수 KB)는 입력 수천 토큰 수준이라 $0.042/M 기준 매우 작지만 0은 아니다. 실측(2026-11-19): 질문 3개·입력 452토큰 1회 = $0.000019. 사용자가 키를 설정한 경우에만 쓰며, 테스트·기본 실행은 네트워크를 쓰지 않는다. 각 응답의 `usage.cost`는 공급자 객체의 `last_usage`에 남는다.

## 6. 실호출 테스트(opt-in)

`CINEFORGE_LIVE=1`과 `OPENROUTER_API_KEY`가 있을 때만 `tests/test_live_openrouter.py`가 돈다(Jev 1회 + 기본 생성 모델 1회). 기본 `pytest`·CI에서는 건너뛴다.
