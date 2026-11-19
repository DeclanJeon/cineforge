# 19. 엔진 카탈로그 — 16개 엔진과 6개 추가 계층

원본: `cineforge/data/pipeline.yaml`의 `engines`, `layers`. 엔진은 기능 단위이고, 실제 수행은 스킬(호스트 에이전트) 또는 CineForge 모듈이 한다.

| 엔진 | 이름 | 영역 | 담당 스킬 | CineForge 모듈 | 사용 단계 | 상태 |
|---|---|---|---|---|---|---|
| E01 | 트렌드·소재 발굴 엔진 | 기획 | topic-demand-selection, searching-social-media | intake.py(요구 분석) · 소재 발굴은 스킬 | S00_intake | 부분 구현 |
| E02 | 콘셉트 라이브러리 | 기획 | concept-intake-design | taxonomy.py, data/taxonomy.yaml | S01_selection | MVP 구현 |
| E03 | 콘셉트 조합 엔진 | 기획 | concept-intake-design | concept.py combine/compatibility/direction_rules | S02_concept | MVP 구현 |
| E04 | 아이디어 평가 엔진 | 기획 | concept-intake-design, topic-demand-selection | concept.py evaluate(Jev Score) | S02_concept | MVP 구현 |
| E05 | 스토리 구조 엔진 | 시나리오 | developing-video-synopses | planner.py NARRATIVE_TEMPLATES | S03_plan, S04_story | MVP 구현 |
| E06 | 캐릭터·관계 엔진 | 시나리오 | designing-video-character-sheets, designing-character-personas | ssot.py character | S03_plan, S05_character_world | MVP 구현 |
| E07 | 세계관·설정 엔진 | 시나리오 | video-production-assets | ssot.py world | S03_plan, S05_character_world | MVP 구현 |
| E08 | 대본·대사 엔진 | 시나리오 | video-production-assets | planner.py(대사), ssot.py story | S04_story | MVP 구현 |
| E09 | 연출 디렉팅 엔진 | 연출 | camera-spatial-design, silent-visual-storytelling | ssot.py camera, concept.direction_rules | S03_plan, S06_storyboard | MVP 구현 |
| E10 | 스토리보드 엔진 | 연출 | storyboarding-video | ssot.py scene, assets.frames | S06_storyboard | MVP 구현 |
| E11 | 타이밍·리듬 엔진 | 연출 | animatic-direction | planner.split_durations, qa CQ07 | S03_plan, S06_storyboard | MVP 구현 |
| E12 | 에셋·SSOT 엔진 | 제작 | video-production-assets, designing-video-character-sheets | assets.registry, ssot.SSOTStore | S05_character_world, S07_assets | MVP 구현 |
| E13 | 생성 모델 라우팅 엔진 | 제작 | creative-production, ai-camera-control | assets.image_prompts/video_prompts, providers/router(판단 모델 라우팅) | S07_assets, S08_generation | MVP 구현 |
| E14 | 영상 생성·합성 엔진 | 제작 | higgsfield-generate, higgsfield-video-replicate, storytelling-with-still-images | 인계 패킷만(handoffs/S08) | S08_generation | 설계·인계 |
| E15 | 편집·사운드 엔진 | 후반 | video-production-assets | 인계 패킷만(handoffs/S09) | S09_edit | 설계·인계 |
| E16 | 품질 평가·개선 엔진 | 검수 | video-production-assets, creative-production | qa.py, reviews/* | S10_qa | MVP 구현 |

## 6개 추가 계층

| 계층 | 이름 | 구현 위치 | 상태 |
|---|---|---|---|
| L1 | 제약조건·적합성 검사 | concept.compatibility(C001–C016, C100), qa.constraints(CQ10·CQ11), G1/G2 | MVP 구현 |
| L2 | 버전·변경 영향 관리 | ssot.SSOTStore(해시 기반 버전·잠금·history.jsonl), ssot.impact, pipeline.apply_impact | MVP 구현 |
| L3 | 연속성 검증 | qa.continuity(CQ01–CQ08), qa.identity(CQ09) | MVP 구현 |
| L4 | 비용·리소스 최적화 | qa.cost_plan(컷별 난이도→티어), 실제 비용 계산은 공급자 견적 필요 | 부분 구현 |
| L5 | 권리·안전 검수 | qa.rights_safety(RS01–RS04) | MVP 구현(규칙 기반) |
| L6 | 성과 피드백 | S12_feedback 단계 자리만 | 설계만 |
