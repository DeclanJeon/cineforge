# 02. 아키텍처

## 1. 구성 요소

```mermaid
flowchart LR
  U[사용자] -->|요구사항·선택·승인| CLI[cineforge CLI]
  CLI --> PIPE[pipeline.Project<br/>상태 기계]
  PIPE --> INT[intake<br/>9개 판단 요소]
  PIPE --> SEL[selection<br/>대화형 선택]
  PIPE --> CON[concept<br/>조합·적합성·평가]
  PIPE --> PLN[planner + render<br/>기획안]
  PIPE --> SSOT[ssot<br/>8종 SSOT·버전·영향]
  PIPE --> AST[assets<br/>에셋·프레임·프롬프트·큐시트]
  PIPE --> QA[qa<br/>연속성·제약·권리·비용]
  PIPE --> PRG[progress<br/>작업률·진행률]
  INT & SEL & CON & PLN --> RT[providers.router]
  RT --> JEV1[Jev 1.14 via OpenRouter]
  RT --> JEV2[Jev 1.14 TypeSafe 직접]
  RT --> HOST[호스트 에이전트<br/>agent_io 요청/응답]
  RT --> HEU[규칙 기반 / 목업]
  RT --> GEN[OpenRouter 생성 모델<br/>CINEFORGE_GEN_MODEL]
  PIPE -->|handoffs/*.json| SK[contents-production-skills<br/>creative-production 총괄]
  SK -->|증거 파일 + cineforge complete| PIPE
  DATA[(data/taxonomy.yaml<br/>rules.yaml<br/>pipeline.yaml<br/>schemas)] --> PIPE
```

## 2. 실행 흐름

```mermaid
sequenceDiagram
  participant U as 사용자
  participant C as CineForge
  participant R as 공급자 라우터
  participant A as 호스트 에이전트/스킬
  U->>C: cineforge new "요구사항" --project-id comedy-short
  C->>R: 9개 요소 판정(Noul)
  R-->>C: 판정(Jev → 호스트 → 규칙)
  C->>U: 열린 축만 한 번에 질문
  U-->>C: 선택(또는 ?, !)
  C->>R: 추천(Choice)·평가(Score)
  C->>C: 조합·적합성·연출 규칙·평가
  C->>R: 기획안 생성(generation)
  R-->>C: plan.json (스키마 검증)
  C->>U: G1 기획안 검수(또는 사전 위임)
  C->>C: SSOT 8종 → 에셋·프레임·프롬프트·큐시트 → G2 검수
  C->>A: handoffs/S08_generation.json (권한 있을 때)
  A-->>C: 결과 파일 + cineforge complete
  C->>A: S09 편집 / S10 검수 인계
  C->>U: G3 최종 승인 → S11 출력·이력
```

## 3. 폴더 구조(프로젝트)

```
productions/<project_id>/
  project.json        요청·공급자 모드·버전
  authority.json      사용자가 준 승인·권한만
  progress.json       단계 상태·작업·검수·진행률
  history.jsonl       모든 이벤트(시간순)
  intake.json  selection.json  concept.json  plan.json  plan.md  script.md
  ssot/{concept,story,character,world,scene,camera,motion,audio}.json
  assets/{asset_registry,frames,image_prompts,video_prompts,sound_cue_sheet}.json
  reviews/{plan_review,preproduction_review,final_qa,user_review}.json
  handoffs/<stage>.json
  agent_io/requests|responses/<task>.json
  provider_log.json   공급자 선택·폴백 기록(키 없음)
```

## 4. 설계 원칙

1. **선택은 앞에서 한 번** — 이후 단계는 선택·콘셉트를 상속하고 질문하지 않는다. 승인 게이트만 남는다.
2. **판단과 생성의 분리** — Jev는 typed 판단 전용, 문장은 호스트 AI/생성 모델(ADR-003).
3. **실행은 스킬에게** — CineForge는 유료 API를 직접 부르지 않고 인계 패킷과 증거 기반 완료만 관리(ADR-005).
4. **데이터 주도** — 분류·규칙·파이프라인은 YAML, 산출물은 JSON 스키마.
5. **오프라인 기본** — 키가 없으면 규칙 기반·목업으로 끝까지 시험 가능.
