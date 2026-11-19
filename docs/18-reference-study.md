# 18. 레퍼런스 조사

참고 저장소의 코드·문구는 가져오지 않았다. 구조와 아이디어만 비교했다(외부 내용은 데이터로만 읽음).

## Pixelle-Video (AIDC-AI, Apache-2.0) — t.co 링크의 실제 대상

- 흐름: 주제 → 대본 → 이미지 기획 → 프레임 처리 → 합성. 템플릿과 ComfyUI/직접 API 모델.
- 배운 점: 단계를 고정된 파이프라인으로 두고 템플릿으로 출력 형식을 통일. → CineForge의 `pipeline.yaml` + 템플릿.
- 다른 점: Pixelle은 자동 생성까지 한 번에 간다. CineForge는 생성 앞에서 사용자 권한을 요구하고 스킬에 인계한다.

## Jellyfish (Forget-C, Apache-2.0, FastAPI + React)

- 대본 → 샷 분해 → 후보 확정 → 샷 `ready` → 생성 작업공간. 캐릭터·장면·소품·의상 엔티티, 비동기 작업 센터, 샷 상태 pending/generating/ready.
- 배운 점: 엔티티(캐릭터·소품·의상·장소)를 먼저 확정하고 샷은 그것을 참조. 샷 단위 상태. → SSOT character/world, 에셋 목록, 컷 시작/끝 상태.

## waoowaoo (waooAI, Elastic License 2.0, Next.js/Prisma/Temporal)

- OperationPlanSnapshot → ApprovalGrant(계획·견적 해시) → OperationExecution. Task 진행률, TaskEvent, 체크포인트, 리소스 버전·계보. OpenRouter를 API 공급자로 사용.
- 배운 점: 승인을 계획/견적 해시에 묶기, 작업 이벤트와 진행률, 리소스 버전 계보. → CineForge의 authority.json, history.jsonl, SSOT 해시 버전·upstream_versions, 진행률.
- 주의: Elastic License 2.0은 재배포·호스팅 제약이 있어 코드 재사용은 하지 않는다.

## 반영 요약

| 아이디어 | 출처 | CineForge |
|---|---|---|
| 고정 단계 + 템플릿 | Pixelle | pipeline.yaml, templates/ |
| 엔티티 먼저, 샷은 참조 | Jellyfish | SSOT character/world → scene |
| 샷 상태 | Jellyfish | 컷 start/end state, 단계 상태 |
| 승인 해시·견적 | waoowaoo | authority + spend_ceiling, 인계 패킷 cost_plan |
| 작업 이벤트·진행률 | waoowaoo | history.jsonl, progress 두 비율 |
| 리소스 버전 계보 | waoowaoo | SSOT 버전, upstream_versions, impact |
