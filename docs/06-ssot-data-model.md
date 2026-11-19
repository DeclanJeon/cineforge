# 06. SSOT 데이터 모델

모듈: `cineforge/ssot.py`, 스키마: `cineforge/data/schemas/ssot_*.schema.json`.

## 1. 8종 SSOT

| 종류 | 담는 것 | 의존(상위) |
|---|---|---|
| concept | 제목줄, 부제, 조합, 감정 곡선, 연출 규칙, 금지 소품, overrides, 평가 | — |
| story | 로그라인, 시놉시스, 후킹, 타임라인, 비트, 복선 | concept |
| character | 인물(ID, 이름, 나이, 역할, 페르소나, 외형, 의상, 목소리, 정체성 앵커, 동의 정보) | concept |
| world | 시대, 세계관, 장소(LOC ID), 소품, 규칙 | concept |
| scene | 씬·컷(ID, 구간, 길이, 화면 구성, 대사·화자, 등장 인물, 시작/끝 상태, 상태 변화) | concept, story, character, world |
| camera | 컷별 샷 크기, 렌즈 느낌, 앵글, 움직임, 시선축 | concept, scene |
| motion | 컷별 동작, 속도, 방향 | concept, scene |
| audio | 목소리 유형(대사/무음), 큐(BGM·SFX·DIALOGUE·AMB) | concept, story, character, scene |

## 2. 문서 봉투(envelope)

```json
{"ssot_type": "scene", "version": 3, "updated_at": "2026-11-19T23:22:17+09:00",
 "source_hash": "40f4299746707852", "locked": false, "depends_on": ["concept", "story", "character", "world"],
 "upstream_versions": {"concept": 1, "story": 2, "character": 1, "world": 1},
 "data": { … }}
```

- **버전**: `data`의 해시가 바뀔 때만 올라간다(같은 내용 재작성은 버전 유지).
- **잠금**: `locked: true`면 쓰기 시 `PermissionError`. `cineforge lock/--unlock`.
- **이력**: 프로젝트 `history.jsonl`에 `ssot_write` 이벤트(종류·버전·해시·시각·영향 대상).
- **depends_on / upstream_versions**: 상위 SSOT 종류와, 작성 시점의 상위 버전. 프롬프트는 `ssot_versions`로 자기가 참조한 버전을 기록한다.

## 3. 컷 상태(연속성의 근거)

```json
{"cut_id": "S01C03", "start_state": {"holding": {"CH01": {"left": null, "right": "펜"}},
  "positions": {"CH01": "left"}, "wardrobe": {"CH01": "W1"}, "lighting": "…"},
 "end_state": {"holding": {"CH01": {"left": null, "right": null}}, …},
 "state_changes": ["도현이 펜을 떨어뜨림"]}
```

기획안 컷의 `state.start`/`state.end`/`changes`가 있으면 쓰고, 없으면 앞 컷의 끝 상태를 이어받는다. 같은 씬 안에서 앞 컷 끝 ≠ 이번 컷 시작이고 상태 변화 기록이 없으면 연속성 오류(CQ02–CQ04).

## 4. 변경 영향 분석

```
concept  → story, character, world, scene, camera, motion, audio, plan
story    → scene, audio
character→ scene, image/video prompts, frames, audio
world    → scene, image/video prompts
scene    → camera, motion, frames, image/video prompts, sound cue sheet
camera   → frames, video prompts
motion   → video prompts
audio    → sound cue sheet
```

`cineforge impact <p> character --apply` → 영향 단계(S05·S06·S07 등)를 `stale`, 이후 게이트·외부 단계를 `pending`으로 되돌린다. 재생성은 영향 범위만(비용 L4).

## 5. 다른 산출물 스키마

plan, selection, intake, prompts, frames, asset_registry, sound_cue_sheet, qa_report, progress, handoff, authority — 모두 `data/schemas/`에 있고 쓰기 전에 검증한다.
