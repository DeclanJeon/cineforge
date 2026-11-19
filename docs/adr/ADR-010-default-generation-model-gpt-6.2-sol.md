# ADR-010 기본 생성 모델: `openai/gpt-6.2-sol`

- 상황: ADR-008에서 기본 기획안 작성 모델을 `openai/gpt-6.1-terra`로 정했다. 2026-11-20 사용자가 "기획안 작성모델은 6.2 sol이 기본 모델"이라고 지정했다.
- 확인: 2026-11-20 OpenRouter `/api/v1/models` 실시간 목록에서 `openai/gpt-6.2-sol`(표시 이름 "OpenAI: GPT-6.2 Sol")을 확인. 100만 토큰당 입력 $2 / 출력 $10, 컨텍스트 1.05M, 최대 출력 128K, `response_format` 지원. 같은 계열의 `openai/gpt-6.2-sol-pro`(같은 가격), `:batch` 변형(반값, 배치 전용)은 기본값으로 쓰지 않는다.
- 결정: `DEFAULT_GEN_MODEL = "openai/gpt-6.2-sol"`. 60초 기획안 1편(입력 약 5천·출력 약 6천 토큰) ≈ $0.07.
- 동작(ADR-008과 동일): `OPENROUTER_API_KEY`가 있으면 생성 공급자가 켜지고 모델은 `CINEFORGE_GEN_MODEL` → 기본값 순. `CINEFORGE_GEN_MODEL=off`(또는 `none`·`0`·`false`)면 문장 생성을 끄고 호스트 AI/목으로 넘어간다. 키가 없으면 절대 호출하지 않는다.
- 검증: 오프라인 테스트(`tests/test_providers.py::test_generation_default_model_and_override`)로 기본값·덮어쓰기·off를 고정. 이 변경에서는 비용을 쓰지 않으려고 실호출을 하지 않았다. 요청 형식은 ADR-008 때 실호출로 확인한 OpenRouter chat/completions와 같다. 다음 opt-in 실행: `CINEFORGE_LIVE=1 python -m pytest -q tests/test_live_openrouter.py`.
- 대체: ADR-008.
