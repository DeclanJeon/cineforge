# 08. CLI UX

## 1. 명령

| 명령 | 하는 일 |
|---|---|
| `cineforge new "요구사항" [옵션]` | 프로젝트 생성 → 요구사항 분석 → 선택 → 가능한 데까지 실행 |
| `cineforge select <p> [--set …]` | 기존 프로젝트의 선택을 (다시) 진행, S01부터 재실행 대상으로 |
| `cineforge run <p> [--until 단계] [--provider 모드]` | 멈춘 지점부터 이어서 실행 |
| `cineforge status <p> [--json]` | 진행률·작업률·단계별 상태·검수·담당 스킬 |
| `cineforge accept <p> plan|preproduction|final` | 게이트 승인 |
| `cineforge grant <p> execution|edit|publish [--spend-ceiling 20USD]` | 실행 권한 기록 |
| `cineforge complete <p> <S08…S11> --evidence 파일…` | 외부 단계 완료(증거 필수) |
| `cineforge impact <p> <ssot> [--apply]` | 변경 영향 분석·재실행 표시 |
| `cineforge lock <p> <ssot> [--unlock]` | SSOT 잠금/해제 |
| `cineforge taxonomy [--axis X] [--json] [--export PATH --with-rules]` | 분류 체계 보기·내보내기 |
| `cineforge providers [--provider 모드]` | 판단·생성 공급자 체인과 사용 가능 여부 |
| `cineforge analyze "요구사항"` | 요구사항 분석 결과(JSON)만 |

`new` 옵션: `--provider auto|host|openrouter|mock`, `--preset`, `--set axis=value[,value]`(한국어 라벨 가능, `direction.texture=시네마틱`), `--input-json`, `--non-interactive`, `--confirm-all`, `--script/--scenario/--reference/--lead-character/--voice`, `--no-speech`, `--auto-accept-plan`, `--nonstop`, `--until`, `--projects-dir`, `--project-id`.

폴더명은 `--project-id` 그대로 사용한다. 직접 실행하는 터미널에서는 생략하면 폴더명을 묻고, 비대화형(파이프 또는 `--non-interactive`)에서는 필수다. 호스트 에이전트는 사용자 지정 이름이 없으면 요구사항을 요약한 영문 소문자 슬러그를 `--project-id`로 전달한다. 기존 폴더는 그대로 유지된다.

`cineforge skills [--root PATH]`로 설치를 진단한다. 실제 제작에는 `CINEFORGE_SKILL_PACK` 또는 지원되는 기본 스킬 경로에 유효한 v1 매니페스트가 필요하다. `status --json`은 프로젝트에 고정한 팩을 보여 준다. 기존 팩이 없으면 조회는 가능하고, 변경 작업은 동일한 팩을 복원한 뒤 재개한다.

## 2. 대화형 선택 규칙

- 요청문에서 감지된 축은 묻지 않는다(`--confirm-all`이면 다시 확인).
- 축마다 번호 목록, 기본값, 필수 여부를 보여준다. 여러 개 선택은 쉼표.
- 입력: 번호/라벨 → 선택, Enter → 기본값(선택 축은 건너뛰기), `?` → AI 추천 받기, `!` → 남은 항목 전부 AI에게 맡기기.
- 연출은 8개 하위 축(질감·시점·카메라·표현·편집 리듬·색감/조명·현실감·사운드)을 각각 묻는다.
- 대사 없음 제약이면 사운드 축에서 대사/내레이션 중심은 C100으로 막힌다.
- 자유 입력: 한 줄 아이디어, 주연 캐릭터, 목소리 방침, 레퍼런스.

## 3. 예시 세션(목업 공급자, 비대화형)

```
$ cineforge new "60초 분량의 코미디 숏드라마 … 연출은 시네마틱 실사, 서사 구조는 결말 선공개" --project-id comedy-short --provider mock --non-interactive --nonstop
[요구사항 분석 — 9개 판단 요소]
  대본·각본이 있나?        없음 → AI가 기획안 확정 후 대본을 작성
  …
  영상의 연출은?           일부 → 연출 8개 하위 축·제작 방식 선택
남은 필수 항목 → AI 추천으로 채움: emotion_arc, production_method, aspect
▶ S01_selection … ▶ S08_generation
진행률 ███████████████░░░░░░░░░  63.0%
작업률 ██████████████████░░░░░░  …
S08 이미지·영상·음성 생성  ⛔ blocked  … 'execution' 권한 필요 → cineforge grant <프로젝트> execution
조합된 제작 콘셉트: 60초 코미디 숏드라마 — 시네마틱 실사 연출 · 결말 선공개 서사
  평가: 76.0점 (go) hook=90 feasibility=50 …
기획안: productions/<id>/plan.md
```

## 4. 호스트 AI 모드 세션

```
$ cineforge new "…" --project-id comedy-short --provider host --non-interactive
요구사항 분석에 호스트 에이전트 응답이 필요합니다 …
# 에이전트: agent_io/requests/intake_factors.json 을 읽고 agent_io/responses/intake_factors.json 작성
$ cineforge run productions/<id>      # 다음 요청이 생기면 반복
$ cineforge accept productions/<id> plan
$ cineforge run productions/<id>
```

## 5. 종료 코드

0 정상(대기 포함), 1 사용자 입력·상태 오류(잘못된 --set, 증거 없는 complete 등), 2 인자 오류.
