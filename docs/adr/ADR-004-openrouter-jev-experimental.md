# ADR-004 OpenRouter 경유 Jev 요청 형식은 실험 기능 + 폴백

- 상황: TypeSafe 직접 API 형식은 문서로 확인했지만, OpenRouter chat/completions로 System One 질문 맵을 보내는 형식은 확인하지 못했다. 공개 모델 목록에는 jev-router만 보였다.
- 결정: OpenRouter 공급자는 `{state, questions}` JSON을 user 메시지로 보내고 응답 content를 answers JSON으로 파싱한다. 형태가 다르면 ProviderError → TypeSafe 직접 → 호스트 AI → 규칙 기반으로 폴백하고 이유를 기록한다.
- 검증 방법: 사용자가 키를 설정하고 승인하면 `cineforge providers`와 한 번의 `analyze`로 실호출을 확인한다(유료, 소액).
