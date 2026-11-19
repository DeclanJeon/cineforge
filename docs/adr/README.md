# 16. ADR(설계 결정 기록)

| ADR | 제목 | 상태 |
|---|---|---|
| [001](ADR-001-project-and-stack.md) | 별도 프로젝트 cineforge, Python CLI + YAML/JSON 데이터 | 채택 |
| [002](ADR-002-single-upfront-intake.md) | 선택은 처음 한 번, 이후 게이트만 | 채택 |
| [003](ADR-003-decision-vs-generation.md) | Jev는 판단 전용, 문장 생성은 호스트 AI/별도 모델 | 채택 |
| [004](ADR-004-openrouter-jev-experimental.md) | OpenRouter 경유 Jev 요청 형식은 실험 기능 + 폴백 | 대체됨(ADR-009) |
| [005](ADR-005-skills-execute-media.md) | 유료 생성·편집은 스킬이 실행, CineForge는 인계·증거만 | 채택 |
| [006](ADR-006-new-route-r33.md) | 스킬 저장소에 R33 + concept-intake-design 추가 | 채택(사용자 확인 대기) |
| [007](ADR-007-ssot-hash-versioning.md) | SSOT 해시 기반 버전·잠금·영향 분석 | 채택 |
| [008](ADR-008-default-generation-model.md) | 기본 생성 모델 `openai/gpt-6.1-terra` | 채택 |
| [009](ADR-009-jev-openrouter-decisions-api.md) | OpenRouter 경유 Jev는 Decisions API(`/api/alpha/decisions`) | 채택(실호출 확인) |
