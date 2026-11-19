# 15. 테스트 계획과 결과

## 1. 원칙

- 모두 오프라인: `conftest.py`가 `OPENROUTER_API_KEY`·`TYPESAFE_API_KEY`·`CINEFORGE_GEN_MODEL`·`CINEFORGE_AGENT_MODE`를 지운다. 원격 공급자는 가짜 transport로만 시험한다.
- 실행: `python -m pytest -q` (프로젝트 루트).

## 2. 범위

| 파일 | 확인하는 것 |
|---|---|
| test_taxonomy.py | 사용자 목록 개수(문화권 22, 로맨스 24, 판타지 24, 이야기 성격 23, 서사 12, 형식 12대분류), 길이 4종, 연출 8축, id 유일성, 한국어 라벨 해석, 프리셋·규칙이 실제 항목만 참조 |
| test_intake_selection.py | 샘플 요청 감지(60초·코미디·숏드라마·시네마틱·실사·결말 선공개), "숏드라마" 안의 "드라마" 오검출 방지, 9개 요소, 대사 없음 제약, 한서윤 규칙, --set 한국어·direction, 잘못된 값 거부, 비대화형 채우기, 대화형(?·!) |
| test_concept.py | 콘셉트 조합·평가, 15초+병렬 서사 경고, C001 차단과 override, 1990년대 한국 멜로 팩·금지 소품, C100 |
| test_providers.py | System One 응답 파싱(choice/score 인덱스/noul), 범위 밖 거부, TypeSafe 요청 형태, OpenRouter 산문 응답 → 폴백 + 키 비노출, Jev Decisions API URL·본문·usage, score 연속값→등급, refusal 폴백, 생성 기본 모델·덮어쓰기·off, 생성 요청 형태, 호스트 요청/응답 왕복, 키 없을 때 오프라인, 잘못된 모드 |
| test_plan_ssot_qa.py | 예시 기획안 스키마·P01/P02, 7섹션 렌더, SSOT 8종 + 연속성 무오류, 의도적 소품 불연속 검출(CQ02), 타이밍 불일치(CQ01), 금지 소품(CQ10)·대사 없음(CQ11), 해시 버전·잠금, 영향 체인 |
| test_pipeline_cli.py | 목업 전체 흐름: G1 대기 → accept → G2 대기 → accept → S08 blocked → grant(한도) → waiting_external → 증거 없는 complete 거부 → 증거로 done; --nonstop; 진행률 증가; 호스트 모드 + 예시 기획안 → G2 pass/warn; impact → stale; taxonomy 내보내기 = 스킬 사본(바이트 일치); CLI 목록·providers; 잘못된 --set; 프로젝트 파일에 키 없음 |

스킬 저장소 쪽: `concept-intake-design/scripts/test_concept_check.py`(PyYAML 없으면 skip) — 목록 개수, 규칙 참조 유효성, 깨끗한 선택 통과, 필수 축 누락 표시, C001 차단/override, C100 override 불가, 1990년대 팩, CLI 종료 코드.

## 3. 결과(2026-11-19)

- CineForge: `48 passed`.
- 스킬 저장소: `test_storyboard_document.py` 제외 시 `1160 passed, 7 skipped, 533 subtests passed`. 기준선은 5 failed(라우팅 하네스 3 + Chrome PDF 2) → 하네스 3건 수정. Chrome PDF 2건은 이 머신에서 headless Chrome이 멈추는 환경 문제로 그대로.
- `scripts/check_versions.py`: package 2.61, 26 skills consistent. `scripts/sync_installed.py --dry-run --root /tmp/...`: created=26, 아무것도 쓰지 않음.

## 4. 수동 확인

- 목업 e2e(샘플 요청, --nonstop): S08 앞에서 정지, 평가 76.0(go), 대안 2개.
- 호스트 모드 e2e: 요청 7회 응답 후 예시 기획안으로 G1 대기 → 승인 → G2 warn(CQ07 대사 밀도, RS03·RS04 info).

## 실호출(opt-in)

- `tests/test_live_openrouter.py`: `CINEFORGE_LIVE=1`과 `OPENROUTER_API_KEY`가 모두 있을 때만 실행. Jev 1.14 Decisions 1회 + 기본 생성 모델 1회. 그 밖에는 skip.
