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
| 확인 안 된 점 | OpenRouter 공개 모델 목록(/api/v1/models)에는 jev-router만 보였고 그 endpoint 목록은 비어 있었다. OpenRouter chat/completions로 System One 질문 맵을 보내는 정확한 형식은 문서로 확인하지 못했다 |

결론: Jev는 **판단 전용**(요소 판정·추천·채점)으로 쓰고, 기획안 같은 문장 생성은 호스트 AI 또는 별도 생성 모델이 맡는다(ADR-003). OpenRouter 경유 Jev는 실험 기능이며 실패하면 폴백한다(ADR-004).

## 2. 체인

| 모드 | 판단 체인 | 생성 체인 |
|---|---|---|
| auto(기본) | jev-openrouter → jev-typesafe → (CINEFORGE_AGENT_MODE=1이면) host-agent → heuristic | openrouter-gen → (agent mode) host-agent → mock |
| host | jev-openrouter → jev-typesafe → host-agent | host-agent |
| openrouter | jev-openrouter → jev-typesafe → heuristic | openrouter-gen |
| mock | heuristic | mock |

- 공급자는 키가 있을 때만 `available`. 키: `OPENROUTER_API_KEY`, `TYPESAFE_API_KEY`(환경변수만).
- 생성 모델은 `CINEFORGE_GEN_MODEL`(예: OpenRouter 모델 slug)을 **명시해야만** 켜진다 — 유료 생성 호출의 명시적 opt-in.
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

Jev 판단 1회(질문 1~9개, 상태 수 KB)는 입력 수천 토큰 수준이라 $0.042/M 기준 매우 작지만 0은 아니다. 사용자가 키를 설정한 경우에만 쓰며, 테스트·기본 실행은 네트워크를 쓰지 않는다.
