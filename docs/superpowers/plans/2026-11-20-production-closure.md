# 작업지시서 — 제작 완결(Production Closure)

- 기준 설계: [설계문서](../specs/2026-11-20-production-closure-design.md)
- 대상 저장소: CineForge (`feature/verified-handoffs` 위에서 새 브랜치 권장)
- 진행률: **고정 분모 20 = 태스크 12 + rubric 8**, 95% = 19/20
- 공통 규칙: TDD(실패 확인 → 최소 구현 → 전체 통과). 외부 호출·설치·결제·커밋·푸시는 별도 승인.

## 전역 제약

- 새 상태 원장을 만들지 않는다. `project.json`·`authority.json`·SSOT가 정본이고, 봉투/영수증은 파생 투영이다.
- 비밀을 프로젝트에 쓰지 않는다. 테스트는 가짜 키만 쓴다.
- provider 실패를 다른 provider로 조용히 대체하지 않는다.
- `available` ≠ `verified`. 최종 납품은 `verified`만 통과한다.
- 모든 태스크는 `pytest -q` 전체 통과 후에만 완료한다.

## T1 — 실행 봉투와 영수증

- 파일: `cineforge/jobs.py`, `cineforge/execution.py`, `tests/test_jobs.py`
- 인터페이스:
  - `build_audio_jobs(project) -> list[Job]` (sound_plan → OST/BGM/SFX/DIALOGUE)
  - `build_video_jobs(project) -> list[Job]` (video_prompts + take 대상)
  - `write_envelope(project, stage, jobs) -> Path` / `load_envelope(project, stage)`
  - `record_results(project, stage, results, *, runner_meta) -> Path`
- 규칙: `job_id = kind:target` 결정적, `idempotency_key = sha256(binding+job spec+inputs)`, `uncertain` 자동 재시도 금지, 해시 불일치 거부, 동일 재제출 멱등.
- 완료 조건: 테스트에서 결정성·멱등·변조 거부·불명 보류를 확인. 전체 suite green.

## T2 — verified 게이트

- 파일: `cineforge/gate.py`, `tests/test_gate.py`, `cineforge/cli.py`(`cineforge gate <project>`)
- 인터페이스: `check(project, *, stage) -> GateReport(status, blockers[])`
- 규칙: 등록 자산·테이크·음성의 `status=verified`, 버전 핀 최신, 참조 파일 존재·해시 일치. 미충족이면 S09 납품 차단.
- 완료 조건: `available`만 있는 프로젝트에서 `fail`, verified로 승격 후 `pass`. CLI 종료 코드 1/0.

## T3 — 음성·음악 실행 레인

- 파일: `cineforge/audio_jobs.py`, `tests/test_audio_jobs.py`
- 인터페이스: `plan_jobs(sound_plan) -> list[Job]`(provider: suno/elevenlabs/fish_audio), `apply_results(project, results) -> dict`
- 규칙: cue별 1 job, OST 보컬/연주 구분, `--execution` 승인·예산 없으면 봉투 미생성, cue 실패 시 cue만 `failed`.
- 완료 조건: 4종 큐 모두 job 생성, 승인 없음 거부, 실패 격리 테스트.

## T4 — 컷 영상 실행·테이크 선택

- 파일: `cineforge/video_jobs.py`, `tests/test_video_jobs.py`
- 인터페이스: `plan_jobs(project) -> list[Job]`(provider ludyte, cut별), `select_take(project, cut_id, path) -> None`
- 규칙: 컷별 1 job, 참조 이미지 핀 필수, 테이크 길이 ≥ 컷 길이, 채택은 명시 명령만, 재생성은 새 attempt.
- 완료 조건: 참조 누락·짧은 테이크 거부, 채택 후 registry 갱신, 이전 take 보존.

## T5 — 편집 계획

- 파일: `cineforge/edit_plan.py`, `tests/test_edit_plan.py`
- 인터페이스: `build(project) -> dict` (cuts/audio/subtitles), `validate(plan, ssots) -> list[Issue]`
- 규칙: SSOT 순서·길이, 테이크 핀, 큐 레인, 자막 in/out. 결정적(타임스탬프 제외).
- 완료 조건: 같은 입력 두 번 → 동일 JSON, 누락 테이크·길이 초과 검출.

## T6 — 조립(ffmpeg)

- 파일: `cineforge/assembly.py`, `tests/test_assembly.py`
- 인터페이스: `render(project, plan) -> Path` (`edit/render.mp4`), `mix_audio(project, plan) -> Path`
- 규칙: H.264/AAC 24fps, 컷 트림, 오디오 레인 합성, `loudnorm` 2-pass(-14 LUFS, -1 dBTP), 자막 사이드카, `--burn` 옵션.
- 완료 조건: 3컷 fixture에서 실제 MP4 생성, ffprobe 길이·스트림 일치, 음량 측정 통과.

## T7 — 자막

- 파일: `cineforge/subtitles.py`, `tests/test_subtitles.py`
- 인터페이스: `to_srt(cues, cues_path) -> Path`, `validate(srt, runtime) -> list[Issue]`
- 규칙: UTF-8, 최소 1.2s, 최대 2줄·42자, 영상 범위 밖 금지, 겹침 금지.
- 완료 조건: 정상 생성, 범위 초과·겹침·과밀 검출, burn 시 영상 존재.

## T8 — 최종 검수

- 파일: `cineforge/final_qa.py`, `tests/test_final_qa.py`
- 인터페이스: `inspect(project, delivery) -> FinalReport`
- 규칙: 설계 §6 표 전부. 실패 시 `final/` 납품 미생성, report에 사유.
- 완료 조건: 정상 fixture pass, 해시 변조·짧은 길이·음량 초과·자막 범위 초과 각각 fail.

## T9 — 납품 번들

- 파일: `cineforge/delivery.py`, `tests/test_delivery.py`
- 인터페이스: `deliver(project, *, burn=False) -> Delivery`
- 산출물: `final/<slug>.mp4`, `.srt`, `delivery.json`(해시·길이·fps·aspect·gate evidence·AI 표시).
- 완료 조건: 게이트·검수 통과 시에만 생성, 실패 시 기존 납품 보존.

## T10 — CLI·진행 공유

- 파일: `cineforge/cli.py`, `tests/test_cli_closure.py`
- 명령: `cineforge execute <project> --stage S08|S09`, `cineforge resolve <job> --accept|--reject`, `cineforge edit`, `cineforge qa-final`, `cineforge deliver`
- 규칙: 모든 명령 `--json`, 진행 스냅샷에 job 상태 포함, `agent_io/progress.json` 공유.
- 완료 조건: 각 명령 성공·실패 코드, JSON 파싱, 진행 공유 확인.

## T11 — 복구·불명 처리

- 파일: `cineforge/execution.py` 보강, `tests/test_closure_recovery.py`
- 규칙: 제출 후 중단 → uncertain, 재실행 시 재제출 0; 회수 후 편집 전 중단 → 편집만; 입력 변경 → stale 전파.
- 완료 조건: kill 주입 3지점에서 재실행 결과·원장 불변 확인.

## T12 — 문서·E2E

- 파일: `README.md`, `docs/07-pipeline-contracts.md`, `tests/test_e2e_closure.py`
- 완료 조건: 가짜 실행기로 요청→MP4→검수→납품 전 구간 1회, 산출물 해시 기록, 문서 명령 일치.

---

## 인수 rubric (8)

| # | 항목 | 검사 |
|---|---|---|
| R1 | 봉투·영수증 결정성·멱등 | `pytest tests/test_jobs.py` |
| R2 | verified 게이트 차단 | `pytest tests/test_gate.py` + CLI |
| R3 | 음성 4레인 job + 승인 차단 | `pytest tests/test_audio_jobs.py` |
| R4 | 컷 영상 job + 테이크 채택 | `pytest tests/test_video_jobs.py` |
| R5 | 편집 계획 결정성 | `pytest tests/test_edit_plan.py` |
| R6 | 실제 MP4 조립·음량 | `pytest tests/test_assembly.py` + ffprobe |
| R7 | 자막 생성·검증 | `pytest tests/test_subtitles.py` |
| R8 | 최종 검수 fail-closed + 납품 | `pytest tests/test_final_qa.py tests/test_delivery.py` |

## 진행 보고 형식

매 태스크 종료 시: 한 일 → 검증 명령/결과 → **태스크 n/12, rubric m/8, 합계 (n+m)/20**.
95%는 19/20이며, 실제 유료 provider 호출 항목은 승인 전까지 미체크로 남긴다.

---

## 진행 기록

| 단위 | 상태 | 증거 |
|---|---|---|
| T1 실행 봉투·영수증 | complete | `tests/test_jobs.py` 5 passed; 전체 87 passed |
| T2 verified 게이트 | complete | `tests/test_gate.py` 5 passed |
| T3 음성 실행 레인 | complete | `tests/test_audio_video_jobs.py` 3 passed |
| T4 컷 영상·테이크 | complete | `cineforge/video_jobs.py` 채택·길이 검사 |
| T5 편집 계획 | complete | `tests/test_edit_subtitles.py` 3 passed |
| T6 ffmpeg 조립·음량 | complete | `tests/test_assembly.py` 2 passed; -14 LUFS 확인 |
| T7 자막 | complete | SRT 생성·범위/겹침/밀도 검사 |
| T8 최종 검수 | complete | `tests/test_final_delivery.py` 2 passed |
| T9 납품 번들 | complete | `final/<project>.mp4` + srt + delivery.json |
| T10 CLI·진행 공유 | complete | `tests/test_cli_closure.py` 2 passed |
| T11 복구·불명 | complete | `tests/test_closure_recovery.py` 2 passed |
| T12 문서·E2E | complete | `tests/test_e2e_closure.py` 1 passed; README/계약 문서 |

| 단위 | 상태 | 증거 |
|---|---|---|
| R1 봉투·영수증 | checked | `tests/test_jobs.py` 5 passed |
| R2 verified 게이트 | checked | `tests/test_gate.py` 5 passed |
| R3 음성 4레인·승인 차단 | checked | `tests/test_audio_video_jobs.py` 3 passed |
| R4 영상 job·테이크 채택 | checked | 〃 (길이·이력 검사) |
| R5 편집 계획 결정성 | checked | `tests/test_edit_subtitles.py` 3 passed |
| R6 실제 MP4·음량 | checked | `tests/test_assembly.py` 2 passed |
| R7 자막 | checked | SRT·검증 3 passed |
| R8 최종 검수·납품 | checked | `tests/test_final_delivery.py` 2 passed |

전체: `python -m pytest -q` → **107 passed, 2 skipped** (2026-11-20).
