# 09. 진행·검수 보고

## 1. 두 가지 비율

- **작업률(task rate)** = 완료된 작업 수 / 전체 작업 수 × 100. 단계마다 `tasks`(pipeline.yaml)가 있고, 단계가 끝나면 모두 done, 게이트 대기 중이면 자동 검수 작업만 done.
- **진행률(progress rate)** = Σ(단계 가중치 × 단계 완료도) / Σ가중치 × 100. 생성(20)·스토리보드(10)·에셋(10)처럼 무거운 단계의 비중이 크다.
- 건너뛴 단계(S12 등)는 두 비율의 분모에서 뺀다.

## 2. 표시

```
프로젝트 demo — 현재 단계: S08_generation
진행률 ███████████████░░░░░░░░░  63.0%   (단계 가중치 기준)
작업률 ██████████████████░░░░░░  75.0%   (완료 작업 / 전체 작업)

단계                        상태                 작업  검수    담당 스킬
S02 콘셉트 조합·적합성·평가         ✅ done            4/4    PASS  concept-intake-design
G1  기획안 검수 게이트            🙋 waiting_user    1/2    PASS  creative-production
    └ plan.md 검토 후 `cineforge accept <프로젝트> plan`
S08 이미지·영상·음성 생성          ⛔ blocked         0/4    -     higgsfield-generate, creative-production
    └ 'execution' 권한 필요 → …
```

아이콘: ✅ done · ⏳ running · · pending · ⛔ blocked · 🙋 waiting_user · 🤖 waiting_agent · 🔌 waiting_external · ♻️ stale · ❌ failed · ⤼ skipped. 검수: PASS/WARN/FAIL/-.

`status --json`은 `progress.json` 그대로(단계별 status, tasks, qa{status,counts}, started_at, finished_at, note, provider, evidence, 그리고 task_rate, progress_rate).

## 3. 검수 보고서(qa_report.schema.json)

```json
{"gate": "G2_preproduction_review", "status": "warn", "checked_at": "…",
 "issues": [{"rule": "CQ07", "severity": "warn", "target": "S01C02", "message": "대사 밀도 6.7음절/초 > 5"}],
 "summary": {"counts": {"error": 0, "warn": 1, "info": 2}, "cost_plan": {…}, "ssot_versions": {…}}}
```

- `status`: error가 하나라도 있으면 fail, 아니면 warn이 있으면 warn, 아니면 pass.
- 보고서 위치: `reviews/plan_review.json`(G1), `reviews/preproduction_review.json`(G2), `reviews/final_qa.json`(S10, 스킬이 작성), `reviews/user_review.json`(G3).
- S02·S03의 적합성·사전 점검 결과도 단계 `qa`에 요약된다.

## 4. 이력

`history.jsonl`에 project_created, stage(상태 변화), ssot_write, authority, accept, complete(증거 경로), impact_applied, reset 이벤트가 시간순으로 쌓인다. `provider_log.json`에는 판단·생성마다 어느 공급자가 쓰였고 폴백이 있었는지(키 없음)가 남는다.
