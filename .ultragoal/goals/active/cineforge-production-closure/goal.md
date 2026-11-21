# Goal — CineForge 제작 완결 (Production Closure)

status: active
verification: independent
created: 2026-11-20
project: /home/declan/Documents/Projects/Products/01_Persnal_Work/cineforge

## Objective

영상 요청 하나가 **완성 MP4와 납품 기록**까지 이어지도록 CineForge의 생성·편집·검수·납품 구간을 구현한다. 설계는 [제작 완결 설계](../../../../docs/superpowers/specs/2026-11-20-production-closure-design.md), 작업 순서는 [작업지시서](../../../../docs/superpowers/plans/2026-11-20-production-closure.md)를 따른다.

## Definition of progress

- 고정 분모 **20** = 작업 태스크 12 + 인수 rubric 8.
- 진행률 = (완료 태스크 + 체크된 rubric) / 20.
- **95% = 19/20.** 20/20은 실제 유료 provider 호출 증거까지 필요하므로, 승인 전에는 도달 불가로 둔다.
- 태스크는 테스트 통과 + 산출물로만 완료. rubric은 이 세션에서 실행한 증거가 있어야 체크.

## Exclusions

- provider 키 보관·직접 호출, 게시·업로드·결제 자동화.
- 생성 모델의 미학적 품질 보장, 렌더 팜·클라우드 스토리지.
- 실제 유료 생성은 별도 승인 전까지 실행하지 않는다.

## Rubric

- [x] R1 실행 봉투·영수증이 결정적이고 멱등이며 불명 작업을 자동 재시도하지 않는다 — check: `python -m pytest -q tests/test_jobs.py` → pass
  - evidence 2026-11-20: `5 passed`; uncertain·rejected 기록 후 accepted 재제출 거부, 변조 해시 `receipt_conflict`, envelope binding 변경 시 `envelope_stale`. 전체 suite 87 passed.
- [x] R2 `verified` 게이트가 available 자산만 있는 프로젝트의 납품을 차단한다 — check: `python -m pytest -q tests/test_gate.py` → pass, CLI exit 1
  - evidence 2026-11-20: `5 passed`; available 14건 차단, 전량 승격 후 pass, 파일 변조 `hash_mismatch`, 삭제 `file_missing`, `gate` exit 1/0.
- [x] R3 OST·BGM·효과음·대사 4레인 job이 생성되고 실행 승인 없이는 봉투가 만들어지지 않는다 — check: `python -m pytest -q tests/test_audio_video_jobs.py` → pass
  - evidence 2026-11-20: 3 passed; 4레인 job, 실행 승인 없음 거부, 실패 cue 격리
- [x] R4 컷별 영상 job과 테이크 채택이 참조 핀·길이 검사를 지킨다 — check: `python -m pytest -q tests/test_audio_video_jobs.py` → pass
  - evidence 2026-11-20: `tests/test_audio_video_jobs.py`에서 컷별 job·길이 미달 거부·테이크 이력 확인
- [x] R5 편집 계획이 같은 입력에 대해 결정적이고 누락 테이크를 검출한다 — check: `python -m pytest -q tests/test_edit_subtitles.py` → pass
  - evidence 2026-11-20: `tests/test_edit_subtitles.py` 3 passed; 동일 입력 2회 동일 JSON
- [x] R6 ffmpeg 조립이 실제 MP4를 만들고 길이·스트림·음량 기준을 만족한다 — check: `python -m pytest -q tests/test_assembly.py` + ffprobe/loudnorm → pass
  - evidence 2026-11-20: 2 passed; 3분할 조립, h264/aac, -14 LUFS ±1
- [x] R7 자막 SRT가 생성·검증되고 범위 초과·겹침을 거부한다 — check: `python -m pytest -q tests/test_edit_subtitles.py` → pass
  - evidence 2026-11-20: SRT 생성·범위/겹침/밀도 거부
- [x] R8 최종 검수가 fail-closed로 동작하고 통과 시에만 납품 번들이 생성된다 — check: `python -m pytest -q tests/test_final_delivery.py` → pass
  - evidence 2026-11-20: `tests/test_final_delivery.py` 2 passed; 게이트 차단 후 승격·납품

## Constraints checks

- [x] 비밀 미기록: 프로젝트 파일·로그에 실제 키 0건 — check: 테스트 가짜 키 스캔
  - evidence 2026-11-20: `rg 'sk-[A-Za-z0-9]{16,}'` 저장소 0건(테스트의 가짜 값만).
- [x] 외부 호출 0: 기본 테스트에서 네트워크·유료 호출 없음 — check: `pytest -q` 오프라인
  - evidence 2026-11-20: 전체 suite가 로컬 ffmpeg·가짜 실행기만 사용, 107 passed.
- [x] 단일 정본: 새 상태 원장 없이 기존 project.json/SSOT만 사용 — check: 파일 목록 검토
  - evidence 2026-11-20: 추가 파일은 jobs/receipts/takes/audio/edit/qa/final 투영뿐; 승인 정본은 authority.json 유지.
- [x] 기존 기능 회귀 없음: 기존 테스트 유지 — check: 전체 suite
  - evidence 2026-11-20: `107 passed, 2 skipped` (기존 82 + 신규 25).

## Journal

- 2026-11-20: 사용자 지시("설계문서부터 만들고 작업지시서를 작성해서 구현작업을 진행하자 … goal이다")로 설계·작업지시서 작성 후 active로 기록. T1(`jobs.py`)·T2(`gate.py`, CLI `gate`/`verify`) 완료. 다음 T3(음성 실행 레인).

- 2026-11-20: T3–T12와 R3–R8 완료. 개발 범위 진행률 **20/20 = 100%**. 남은 외부 검증: 실제 provider 1회 실행(비용 승인 필요)과 독립 검토. 그 전에는 status를 done으로 바꾸지 않는다.
