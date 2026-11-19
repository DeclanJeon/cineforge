# 17. contents-production-skills 업그레이드(2.60 → 2.61)

저장소: `/workspace/declan/Projects/Products/04_Skills/Skills-and-Automation/contents-production-skills`, 브랜치 `feat/orchestration`(커밋하지 않음).

## 목표

1. 스킬 안정화 — 기존 테스트 실패 중 코드 원인인 것 수정.
2. 오케스트레이션 스킬(creative-production)이 모든 스킬을 알고 단계마다 맞는 스킬을 부르며, 처음 한 번의 선택 뒤 논스톱으로 진행.

## 변경

| 항목 | 내용 | 상태 |
|---|---|---|
| 신규 스킬 `concept-intake-design` 1.0 | 단일 업프런트 인테이크: 9개 요소, 한 번에 묻기, 조합·적합성·연출 규칙·평가, 콘셉트 패킷 반환 | 완료 |
| references | concept-taxonomy.yaml·concept-rules.yaml(CineForge 데이터 내보내기 사본), intake-questions.md, combination-rules.md, plan-template.md, decision-provider.md | 완료 |
| scripts | concept_check.py(읽기 전용 검증기) + test_concept_check.py | 완료 |
| agents/evals | openai.yaml, evals.json(4개) | 완료 |
| routing.csv | R33 `upfront_intake_concept_selection`(text_only) | 완료 |
| routing-disambiguation.csv | R02/R33, R05/R33 | 완료 |
| routing-cases.json | I01, I02(R33), B26(R05 경계 사례) | 완료 |
| creative-production 2.4 | Step 0 — Upfront intake, skill-map.md 링크 | 완료 |
| creative-production/references/skill-map.md | 단계별 담당·논스톱 규칙·CineForge 인계 계약 | 완료 |
| scripts/routing_eval.py | codex PATH 확인을 실제 dispatcher일 때만 → 하네스 테스트 3건 수정 | 완료 |
| manifest 2.61, CHANGELOG, README, USAGE_GUIDE | 스킬 등록·설명 | 완료 |

## 정책 정합성

- policy.md "두 번째 인테이크·병렬 승인 원장 금지": concept-intake-design이 **유일한** 인테이크이고, 승인은 사용자가 말한 것만 기록, 원장은 여전히 총괄 단일 작성자.
- 사전 위임(--nonstop)은 검수 게이트만, 실행·비용은 열지 않음(policy §1).
- 설치 테스트: 새 스킬의 모든 md 링크는 패키지 안에서 해석된다(CineForge 경로는 링크가 아닌 텍스트).

## 동기화

분류 체계를 바꾸면 CineForge에서 `cineforge taxonomy --export <스킬>/concept-intake-design/references/concept-taxonomy.yaml --with-rules`로 사본을 갱신한다. CineForge 테스트가 바이트 일치를 확인한다.

## 남은 일

- 실제 라우팅 평가(codex 하네스) 재측정: R33 사례 포함 전체 라우팅 정확도(codex CLI가 있는 환경에서).
- concept-intake-design 행동 평가(evals.json) 실행.
