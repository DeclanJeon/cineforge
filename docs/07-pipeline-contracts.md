# 07. 단계 계약(Stage Contracts)

엔진 원본은 `cineforge/data/pipeline.yaml`이다. 단계와 입력·출력·필요 권한·작업 목록·가중치를 고정한다. 담당 스킬과 route는 바인딩된 스킬팩 `manifest.json`에서 읽는다. 아래 담당·route 열은 레거시 매핑 예시다. 계약은 [스킬팩 독립 배포 설계](superpowers/specs/2026-11-24-skill-pack-integration-design.md)를 참조한다. 진행률은 가중치, 작업률은 작업 수로 계산한다(09 문서).

| 단계 | 이름 | 가중치 | 엔진 | 계층 | route | 담당 스킬 | 필요 권한 | 출력 | 작업 |
|---|---|---|---|---|---|---|---|---|---|
| S00_intake | 요구사항 접수·분석 | 3 | E01 |  | — | creative-production | — | intake.json | parse_request, detect_inputs, decide_missing |
| S01_selection | 콘셉트 선택(대화형) | 4 | E02 |  | R33 | concept-intake-design | — | selection.json | ask_axes, resolve_defaults, lock_selection |
| S02_concept | 콘셉트 조합·적합성·평가 | 5 | E03, E04 | L1 | R33 | concept-intake-design | — | concept.json, ssot/concept.json | combine, compatibility_check, evaluate, direction_rules |
| S03_plan | 제작 기획안 | 8 | E05, E06, E07, E09, E11 |  | R05 | developing-video-synopses, orchestrating-video-preproduction | — | plan.json, plan.md | synopsis, hook, timeline, scenes_cuts, characters, production_spec, preflight_checks |
| G1_plan_review | 기획안 검수 게이트 | 2 |  | L1 | — | creative-production | — | reviews/plan_review.json | auto_review, user_accept |
| S04_story | 대본·스토리 SSOT | 8 | E05, E08 |  | R13 | developing-video-synopses, video-production-assets | — | ssot/story.json, script.md | beats, screenplay, dialogue_density |
| S05_character_world | 캐릭터·세계관 SSOT | 8 | E06, E07, E12 |  | R03 | designing-video-character-sheets, designing-character-personas | — | ssot/character.json, ssot/world.json | cast_bible, persona, wardrobe, world_rules, props, locations |
| S06_storyboard | 연출·스토리보드·타이밍 | 10 | E09, E10, E11 |  | R10 | storyboarding-video, camera-spatial-design, animatic-direction, silent-visual-storytelling | — | ssot/scene.json, ssot/camera.json, ssot/motion.json | scene_states, camera_specs, motion_specs, timing |
| S07_assets | 에셋·프롬프트·사운드 큐 시트 | 10 | E12, E13 |  | R13 | video-production-assets, ai-camera-control, creative-production | — | ssot/audio.json, assets/asset_registry.json, assets/frames.json, assets/image_prompts.json, assets/video_prompts.json, assets/sound_cue_sheet.json | asset_registry, start_end_frames, image_prompts, video_prompts, sound_cue_sheet |
| G2_preproduction_review | 프리프로덕션 검수(연속성·제약·권리) | 4 |  | L1, L3, L5 | — | video-production-assets | — | reviews/preproduction_review.json | continuity_rules, constraint_rules, rights_safety, cost_estimate |
| S08_generation | 이미지·영상·음성 생성 | 20 | E13, E14 | L4 | R28 | higgsfield-generate, creative-production | execution | handoffs/S08_generation.json | image_generation, video_generation, audio_generation, take_selection |
| S09_edit | 편집·사운드·합성 | 8 | E15 |  | R31 | video-production-assets | edit | handoffs/S09_edit.json | assembly, sound_mix, color, subtitles |
| S10_qa | 품질 검수 | 6 | E16 | L3 | R20 | video-production-assets, creative-production | — | reviews/final_qa.json | continuity_qa, camera_qa, sync_qa, whole_film_qa |
| G3_user_review | 사용자 최종 검수 | 1 |  |  | — | creative-production | — | reviews/user_review.json | user_accept |
| S11_delivery | 최종 출력·이력 | 2 |  |  | R27 | recording-production-history | — | final/ | package, history |
| S12_feedback | 성과 피드백 | 1 |  | L6 | — | topic-demand-selection, searching-social-media | — | feedback.json | metrics_import, hypothesis |

## 공통 규칙

1. **입력은 앞 단계의 정본 파일만.** 단계는 `selection.json`·`concept.json`·`plan.json`·`ssot/*.json`을 읽고, 자기 출력만 쓴다(단일 작성자: CineForge 프로젝트 폴더의 상태 파일은 CLI만 쓴다).
2. **스키마 검증.** 모든 출력 JSON은 `cineforge/data/schemas/*.schema.json`으로 검증하고, 실패하면 단계는 `failed`.
3. **외부 단계(S08·S09·S10·S11).** CLI는 `handoffs/<단계>.json` 인계 패킷만 만든다. 권한이 없으면 `blocked`, 있으면 `waiting_external`. 호스트 에이전트가 담당 스킬로 실행한 뒤 `cineforge complete <프로젝트> <단계> --evidence <파일...>`로 끝낸다. 증거 파일이 없으면 완료를 거부한다.
4. **게이트(G1·G2·G3).** 자동 검수 결과는 `reviews/*.json`. 자동 검수 통과는 사용자 승인이 아니다. 사용자가 `accept` 하거나, `--nonstop`/`--auto-accept-plan`으로 미리 위임한 경우에만 통과.
5. **에이전트 대기.** 호스트 에이전트 모드에서 판단·생성 응답이 없으면 단계는 `waiting_agent`가 되고 `cineforge run`으로 이어간다.
6. **변경 영향.** SSOT가 바뀌면 `cineforge impact <프로젝트> <ssot> --apply`가 영향 단계를 `stale`로, 이후 게이트·외부 단계를 `pending`으로 되돌린다.

## 인계 패킷 형식(handoff.schema.json)

```json
{
  "stage": "S08_generation",
  "route": "R28",
  "owner_skills": [
    "higgsfield-generate",
    "creative-production"
  ],
  "authority_required": "execution",
  "authority_granted": false,
  "inputs": [
    "ssot/scene.json",
    "plan.json",
    "selection.json"
  ],
  "outputs_expected": [
    "handoffs/S08_generation.json"
  ],
  "packet": {},
  "completion_command": "cineforge complete <프로젝트> S08_generation --evidence <파일...>"
}
```


## 생성 이후 구현 계약 (2.62 이후)

S08 이후의 실행·영수증·편집·검수·납품은 [제작 완결 설계](superpowers/specs/2026-11-20-production-closure-design.md)와 [작업지시서](superpowers/plans/2026-11-20-production-closure.md)가 정한다. 요약: `jobs/<stage>.json`(실행 봉투) → `receipts/<stage>.json`(영수증) → `takes/`, `audio/` → `edit/edit_plan.json` → `edit/render.mp4` → `qa/final_report.json` → `final/delivery.json`. `available`은 납품 근거가 아니며 `verified`만 게이트를 통과한다.
