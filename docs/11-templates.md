# 11. 템플릿

| 템플릿 | 파일 | 생성 위치(자동) |
|---|---|---|
| 기획안 | `templates/plan.template.md` | `plan.md`(render.plan_markdown), `plan.json`(plan.schema.json) |
| 캐릭터 바이블 | `templates/character-bible.template.md` | `ssot/character.json` |
| 에셋 목록·시작/끝 프레임 | `templates/asset-registry.template.md` | `assets/asset_registry.json`, `assets/frames.json` |
| 이미지·영상 프롬프트 | `templates/prompt.template.md` | `assets/image_prompts.json`, `assets/video_prompts.json` |
| 사운드 큐 시트 | `templates/sound-cue-sheet.template.md` | `assets/sound_cue_sheet.json` |

## 기획안 7섹션(사용자 형식)

머리말(제목·로그라인·장르·러닝타임·스타일·핵심 전략·조합·감정 곡선·평가) → 1 시놉시스 → 2 후킹 전략(구간·첫 대사·자막·질문 3개) → 3 전체 타임라인 → 4 씬별 상세 콘티 및 컷 구성 → 5 캐릭터 설정 → 6 촬영·편집·사운드 설계 → 7 제작 전 확인할 사항.

예시 원본: `examples/plans/interviewer-ex-girlfriend.plan.json` — 《면접관이 제 전 여친입니다》 60초·5씬·20컷. 호스트 AI 응답 형식의 기준 예시로 쓰이고, 테스트가 이 파일로 기획안 검증·렌더·SSOT·G2 검수를 확인한다.

## 컷 상태 표기(선택)

```json
"state": {"start": {"holding": {"CH01": {"right": "펜"}}}, "end": {"holding": {"CH01": {"right": null}}},
          "changes": ["도현이 펜을 떨어뜨림"]}
```

적어 두면 시작/끝 프레임과 연속성 검수가 정확해진다. 생략하면 앞 컷 끝 상태를 이어받는다.

## 프롬프트 공통 네거티브

화면 속 글자·자막, 워터마크, 로고, 'Made with AI' 등 코너 라벨, 손가락 변형, 얼굴 변형, 인물 바뀜.
