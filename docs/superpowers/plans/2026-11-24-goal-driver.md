# 목표 기반 실행기 작업지시서

> 구현 담당자: 승인 후 `executing-plans` 또는 `subagent-driven-development`로 아래 항목을 순서대로 수행한다. 현재 문서는 실행 지시 초안이며 제품 변경을 수행한 기록이 아니다.

**Goal:** 스토리보드 요청은 보드에서 멈추고, MP4 요청은 허가된 작업을 진행해 검증된 납품본에서 멈춘다.

**Architecture:** 목표 해석·증거 평가·행동 선택은 분리한다. 기존 단계 실행기와 검수기를 호출하며 호스트는 외부 행동만 수행한다.

**Tech Stack:** 기존 Python CLI, 프로젝트 JSON, pytest, 로컬 FFmpeg, Linux 파일 잠금. 신규 서비스 없음.

**Spec:** [목표 기반 실행 설계](../specs/2026-11-24-goal-driver-design.md)

## 공통 제약과 작업 규칙

- 기준 `b7b3a18`; 작업 전 `git status --short`로 사용자 변경을 확인하고 기존 미커밋 문서와 혼합하지 않는다. 저장소 루트의 `.venv/bin/python -m pytest`를 사용한다.
- 목표 모드는 opt-in. 목표 없는 프로젝트의 파일 생성·CLI 종료 코드·기존 실행 계약을 변경하지 않는다. `nonstop`은 지출 또는 최종 승인이 아니다.
- 각 작업에서 **먼저 테스트 작성 → 해당 테스트만 실행해 의도한 실패 확인 → 최소 구현 → 같은 테스트와 관련 회귀 실행 → 변경점 검토** 순서를 지킨다. 통과 전 다음 작업으로 넘어가지 않는다.
- 위험 검토 초점: 부정 표현(T1), 기존 done 단계의 상한 우회(T3), 응답 유실·중복 제출(T4), 교체된 렌더 승인(T2/T5), 수동 CLI 우회(T5).

## T1. 요청을 검증 가능한 목표로 저장

- [ ] `tests/test_goal_contract.py` 신규: ‘영상은 만들지 말고 보드만’ → `text_storyboard`, ‘보드부터 최종 MP4까지’ → `delivery_mp4`, ‘광고 준비’ → 후보 질문. 이미지 보드·검증 불가능한 조건을 텍스트 보드로 축소하지 않는 사례 추가.
- [ ] `cineforge/goal_contract.py` 신규: `resolve(request: str, kind: str | None) -> dict`로 확정 계약 또는 미해결 후보 반환. `cineforge/data/schemas/`에 기존 명명 관례로 goal 스키마 추가. 알 수 없는 버전·음수 길이·잘못된 화면비 거부. `goal set`은 원문 보존, 명시적 타입 변경 시 revision 증가. 과거 지출 승인을 확대하지 않는다.
- [ ] `.venv/bin/python -m pytest -q tests/test_goal_contract.py tests/test_intake_selection.py`. 인수: 같은 확정 입력은 같은 계약, 모호하면 실행 가능한 목표 없음.

## T2. 읽기 전용 완료 판정

- [ ] `tests/test_goal_evidence.py` 신규: 정상/빈 보드, 중복 컷, 단절된 카메라 참조, 1프레임 경계 안팎, 최종본 변조, 이전 렌더 승인 사례 작성. 조회 전후 모든 프로젝트 파일의 해시·목록이 같아야 한다.
- [ ] `cineforge/goal_evidence.py` 신규: `evaluate(root: Path, goal: dict) -> dict` → `satisfied, unmet, evidence`. S06의 실제 SSOT와 납품 manifest를 읽는다. 경로는 프로젝트 내부로 제한한다. 기술 QA·검수·승인은 현재 파일에 대응해야 한다. 쓰기 작업이 포함된 기존 검사 함수는 순수 판정부를 분리하고 조회에서는 기록하지 않는다.
- [ ] `.venv/bin/python -m pytest -q tests/test_goal_evidence.py tests/test_final_delivery.py`. 인수: 단계 상태나 파일 존재만으로 통과하는 사례 0건.

## T3. 한 단계 실행과 허용 행동 선택

- [ ] `tests/test_goal_driver.py` 신규: S06 done인데 증거가 부족해도 S07에 진입하지 않음, 보드 도달 전후 공급자 **미디어 생성** 호출 0회, 18초 보드의 15초 수정, 고정 컷 수정 거부를 검증한다. 해석을 위한 provider 호출과 생성 호출을 구분한다.
- [ ] `cineforge/pipeline.py`에서 `Project.step(sid: str)` 추출. 기존 `run`과 공유하되 외부 영수증 복구와 대기 동작을 보존한다. 신규 `cineforge/goal_driver.py`의 `decide(root: Path, goal: dict, assessment: dict) -> dict`는 한 번에 하나의 사전 등록 행동/대기 사유만 선택한다. 보드 전용 수정은 총 프레임·최소 1프레임·컷 순서를 보존한다. 같은 실패 반복 및 32행동 상한 테스트 추가.
- [ ] `.venv/bin/python -m pytest -q tests/test_goal_driver.py tests/test_pipeline_cli.py tests/test_closure_recovery.py`. 인수: 기존 `--until`과 기존 프로젝트 동작 유지.

## T4. 작업 발행과 복구

- [ ] `tests/test_goal_attempts.py` 신규: 2개 프로세스가 같은 프로젝트를 실행, 발행 직후 강제 종료, 동일 결과 2회 도착, revision 변경 후 이전 결과 도착. 실제 네트워크 대신 접수 횟수를 기록하는 가짜 실행기 사용.
- [ ] 신규 `cineforge/goal_attempts.py`에 프로젝트 잠금, 원자적 intent 기록, 요청 ID·입력 해시 대조 구현. `goal_driver.drive(root: Path) -> dict`에 연결. 로컬 결과는 영수증으로 복구하고 외부 접수가 불확실하면 `needs_reconciliation`. stale 결과를 현재 증거에 승격하지 않는다. `waiting_external`은 권한 승인과 결과 도착을 구분한다.
- [ ] `.venv/bin/python -m pytest -q tests/test_goal_attempts.py tests/test_jobs.py tests/test_verified_handoff.py`. 인수: 중단 시점과 무관하게 자동 중복 제출 0회, 동시 패자는 busy.

## T5. CLI·후반 제작 연결과 권한 검사

- [ ] `tests/test_goal_cli.py` 신규: `new --goal`, `goal show/set/drive`, 수동 `run`·`execute`·`motion`·`render`·`deliver`로 보드 상한 우회 거절, 종료 코드 0/2/3/4 검사. 해시 없는 구형 승인으로 목표 모드 납품 불가, 비목표 모드는 종전 동작 검증.
- [ ] `cineforge/cli.py`, `pipeline.py` 및 실행 명령 공통 진입부에 목표 상한 검사 연결. 중첩 CLI 프로세스를 띄우지 말고 기존 `edit_plan`, `assembly`, `final_qa`, `delivery` 함수를 호출한다. 권한/승인 대기는 사용자에게 필요한 대상·해시·다음 명령을 반환한다. G3 최종 승인에 실제 사용자 확인 당시 해시를 기록하고 납품 직전 재대조한다. 외부 결과가 필요하면 해당 요청 ID를 반환한다.
- [ ] `.venv/bin/python -m pytest -q tests/test_goal_cli.py tests/test_route_authority.py tests/test_cli_closure.py`. 인수: `show`는 부작용 없음, 승인·검수 증거 자동 작성 없음.

## T6. 요청부터 목표까지 인수 및 운영 문서

- [ ] `tests/test_goal_e2e.py` 신규. 공개 CLI만 사용해 ① 15초 9:16 보드 완료 후 재실행해도 생성 0회 ② MP4 요청→외부 대기→가짜 공급자 결과→로컬 편집·렌더→사용자 확인→납품 ③ 렌더 교체 시 재승인 필요를 재현한다. 테스트는 사용자/호스트 입력만 제공한다. 편집·렌더 순서를 테스트가 대신 지시하면 실패로 간주한다.
- [ ] `README.md`, `docs/05-orchestration-state-machine.md`에 예제와 복구 절차 기록. 무엇이 자동이고 무엇이 사람의 판단인지, `run --until`과 목표 완료가 어떻게 다른지 설명한다.
- [ ] FFmpeg 있는 환경에서 `.venv/bin/python -m pytest -q tests/test_goal_e2e.py -rs` 후 전체 `.venv/bin/python -m pytest -q -rs`. 유료/라이브 테스트는 자격증명 없는 격리 환경에서 실행하지 않는다. 핵심 E2E skip은 통과로 기록하지 않는다. 인계 기록: 실제 명령·결과·skip 사유·남은 제약. 기존 테스트 데이터로 실제 공급자 성공을 주장하지 않는다.

**릴리스 경계:** T1~T4는 내부 기능이다. T5만으로 기본 활성화하지 않는다. T6 인수 후에도 명시적 `--goal`이 있는 프로젝트만 대상으로 한다. 문제 발생 시 신규 사용을 중단하고 기존 수동 경로를 유지하며, 미결 원격 작업과 증거 기록은 삭제하지 않는다.
