# CineForge 설계 문서 색인

CineForge는 "요구사항 한 번 → 선택 한 번 → 이후 논스톱" 영상 제작을 위한 대화형 CLI·엔진이다. `contents-production-skills`의 스킬을 단계마다 정확히 호출하도록 상태·인계·검수를 관리하고, 판단은 OpenRouter의 Jev 1.14(설정 시) 또는 호스트 AI가 맡는다.

| 번호 | 문서 | 내용 |
|---|---|---|
| 01 | [SRS](01-srs.md) | 요구사항 명세(기능·비기능·사용자 스토리·인수 기준) |
| 02 | [아키텍처](02-architecture.md) | 구성 요소, 데이터 흐름, mermaid 다이어그램 |
| 03 | [콘셉트 분류 체계](03-concept-taxonomy.md) | 사용자 목록 전체(형식 12대분류, 문화권 22, 로맨스 24, 판타지 24, 이야기 성격 23, 서사 12 …) |
| 04 | [콘셉트 엔진](04-concept-engine.md) | 조합·적합성·연출 규칙 변환·평가 |
| 05 | [오케스트레이션 상태 기계·스킬 라우팅](05-orchestration-state-machine.md) | 단계 상태 전이, 게이트, 스킬 매핑과 공백 |
| 06 | [SSOT 데이터 모델](06-ssot-data-model.md) | 8종 SSOT, 버전·잠금·영향 분석 |
| 07 | [단계 계약](07-pipeline-contracts.md) | 단계별 입력·출력·권한·작업 |
| 08 | [CLI UX](08-cli-ux.md) | 명령, 대화형 선택 규칙, 예시 세션 |
| 09 | [진행·검수 보고](09-progress-qa-reporting.md) | 작업률·진행률·검수 상태 |
| 10 | [LLM 공급자 라우팅](10-llm-provider-routing.md) | Jev 1.14 조사 결과, 폴백 체인, 호스트 에이전트 프로토콜 |
| 11 | [템플릿](11-templates.md) | 기획안·캐릭터 바이블·에셋·프롬프트·사운드 큐 시트 |
| 12 | [연속성·검수 규칙](12-continuity-qa-rules.md) | P01–P07, CQ01–CQ11, RS01–RS04 |
| 13 | [비용·권리·안전](13-cost-rights-safety.md) | 권한 모델, 비용 티어, 권리·AI 표기 |
| 14 | [로드맵](14-roadmap.md) | 6단계 로드맵과 마일스톤 |
| 15 | [테스트 계획](15-test-plan.md) | 테스트 범위와 결과 |
| 16 | [ADR](adr/README.md) | 설계 결정 기록 |
| 17 | [스킬 업그레이드 계획](17-skills-upgrade-plan.md) | contents-production-skills 2.61 변경 |
| 18 | [레퍼런스 조사](18-reference-study.md) | Pixelle-Video, Jellyfish, waoowaoo |
| 19 | [엔진 카탈로그](19-engine-catalog.md) | 16개 엔진, 6개 계층과 구현 상태 |

데이터 정본: `cineforge/data/taxonomy.yaml`, `rules.yaml`, `pipeline.yaml`, `schemas/*.schema.json`. 문서와 데이터가 다르면 데이터가 우선한다.
