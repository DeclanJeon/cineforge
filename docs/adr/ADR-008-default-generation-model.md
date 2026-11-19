# ADR-008 기본 생성 모델: `openai/gpt-6.1-terra`

> 상태: **대체됨** — ADR-010(2026-11-20 사용자 지정으로 기본값을 `openai/gpt-6.2-sol`로 변경). 아래 후보 비교는 참고용으로 남긴다.

- 상황: Jev 1.14는 판단 전용이라 기획안·로그라인 같은 한국어 문장은 별도 생성 모델이 써야 한다(ADR-003). 지금까지는 `CINEFORGE_GEN_MODEL`을 지정해야만 켜져서, 키를 넣어도 문장 생성이 동작하지 않았다.
- 기준: 한국어 문장력, JSON 출력(`response_format`/structured outputs 지원), 적당한 가격, 긴 컨텍스트.
- 후보(2026-11-19 OpenRouter `/api/v1/models` 실시간 목록, 100만 토큰당 입력/출력):

| 모델 | 가격 | 메모 |
|---|---|---|
| `openai/gpt-6.1-terra` | $1 / $5 | GPT-6.1 중간 등급, 모델 설명에 글쓰기(writing) 작업 명시, 1.05M 컨텍스트, 출력 128K |
| `anthropic/claude-sonnet-5.5` | $2 / $10 | 문장력은 좋지만 2배 비쌈 → 품질 우선 시 대안 |
| `google/gemini-3.8-flash` | $0.825 / $4.125 | 비슷한 가격, 설명이 코딩·에이전트 중심 |
| `anthropic/claude-haiku-5.5`, `openai/gpt-6-luna` | $0.1 / $0.5 | 저가, 긴 기획안 품질은 한 단계 아래 |
| `upstage/solar-pro4` | $0.15 / $0.6 | 한국 회사 모델, 저가 → 비용 우선 시 대안 |

- 결정: 기본값 `openai/gpt-6.1-terra`. 60초 기획안 1편(입력 약 5천·출력 약 6천 토큰) ≈ $0.035.
- 동작: `OPENROUTER_API_KEY`가 있으면 생성 공급자가 켜지고 모델은 `CINEFORGE_GEN_MODEL` → 기본값 순. `CINEFORGE_GEN_MODEL=off`면 문장 생성을 끄고 호스트 AI/목으로 넘어간다. 키가 없으면 절대 호출하지 않는다.
- 검증: 2026-11-19 opt-in 실호출 테스트(`tests/test_live_openrouter.py::test_live_generation_default_model`) 통과.
- 재검토: 가격·모델 목록이 바뀌면 이 ADR과 `cineforge/providers/remote.py`의 `DEFAULT_GEN_MODEL`을 함께 고친다.
