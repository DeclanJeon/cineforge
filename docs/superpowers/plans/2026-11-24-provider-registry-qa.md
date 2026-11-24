# QA — 제작 서비스 선택·전체 에이전트 등록 (2026-11-24, branch fix/demo-gaps @ 64f5aad)

## 실행한 검사
| 검사 | 방법 | 결과 |
|---|---|---|
| 자동 테스트 | pytest 전체 | 306 passed, 2 skipped (기존 266 → +40) |
| `services list` | 실제 PC 설정 읽기 | 108줄, 설치 표시 정상(Ludyte·Higgsfield·Suno·Fish·ElevenLabs·Typecast ✓) |
| `services setup` 미리보기 | runway(OAuth)·fal(API 키)·ludyte(기존)·minimax(로컬)·typecast(CLI)·native | 경우별 add/skip/manual 정상, API 키는 환경변수 이름만 |
| `services setup --yes` | **실제 pi·codex·opencode CLI + 샌드박스 HOME** | pi·opencode·gemini 성공. codex는 등록 후 자동 OAuth 대기로 60초 멈춤 → 수정(64f5aad), 재검사 1.5초 성공 |
| 대화형 CLI | pty로 실제 입력 | 용도별 번호 선택·Enter 기본값 정상, project.json 저장·음성 경로 반영 |
| 에이전트(host) 모드 | 실제 CLI로 new→intake→run | `providers_choice`(user_choice, must_ask_user) 생성 후 waiting_user, 응답 후 재개, user_said 기록 |
| 실제 설정 보존 | QA 전후 4개 설정 파일 바이트 비교 | 변경 없음 |

## QA 중 발생한 사고와 조치
- 개발 중 테스트 1개가 기본 인자로 묶인 실제 실행기를 써서 **사용자 Pi·Codex에 `pika`를 실제 등록**했다. 즉시 `pi mcp remove pika`, `codex mcp remove pika`로 되돌렸고 서버 수(Pi 9, Codex 13, OpenCode 4)가 이전과 같음을 확인했다.
- 재발 방지: 실행기를 호출 시점에 조회하도록 수정, conftest에 실제 에이전트 명령·실제 Gemini 설정 수정을 거부하는 autouse 가드 추가.

## 보완·개선 필요
### 판매·병합 전 필수
1. **영상·이미지·음악·효과음 선택이 아직 생성 단계에 연결되지 않음.** 음성만 대사 경로에 반영된다. 실행 계획의 영상 레인은 ludyte·higgsfield·code-motion만 허용해서, 목록의 46개 영상 서비스 중 나머지는 골라도 S08에서 실행할 수 없다. 범용 MCP 레인과 서비스별 길이·비율 제약 반영이 필요하다.
2. **OpenCode 대상 불일치 위험.** PATH의 opencode는 Flucto 번들(v2.2.6)이고 `opencode.json`에 `mcp.servers` 형식으로 쓴다. 사용자가 실제로 쓰는 `opencode.jsonc`는 `mcp.{이름}` 형식이다. 실제 사용하는 OpenCode를 식별해 그 형식으로 등록해야 한다.
3. **Gemini 판정이 부정확할 수 있음.** 이 PC의 `~/.gemini`는 Antigravity가 쓰는 폴더이고 Gemini CLI는 설치되어 있지 않다. `settings.json`에 쓴 항목을 Antigravity가 읽는지 확인되지 않았다. 에이전트별 실제 설정 경로 판별이 필요하다.
4. **미설치 서비스를 골라도 경고가 없음.** 선택 직후 `services setup` 안내를 하거나, S08 전에 미설치·미로그인 상태를 차단해야 한다.
5. **cineforge-production 스킬 갱신.** user_choice를 사용자에게 그대로 전달하라는 규칙을 스킬에 넣어야 한다(병합 후).

### 개선
6. 대화형 목록이 길다(영상 46개). 설치된 것과 추천만 먼저 보이고 `a`=전체, 검색어 필터를 지원하면 좋다.
7. 이미 등록된 로컬/CLI 서비스(Pi의 typecast)를 "manual"로 표시한다. 이름이 같으면 "이미 등록됨"으로 표시해야 한다.
8. 레지스트리 신선도: 15개만 공식 페이지로 직접 확인했고 나머지는 mcp.film 확인일에 의존한다. `services verify`(OAuth 메타데이터·응답 확인) 명령으로 주기 검증을 권장한다. Vidu 인증 방식 미확인, Replicate는 SSE라 제외.
9. 실제 CLI로 검증하지 못한 경로: Claude Code(`claude mcp add`), Gemini CLI(`gemini mcp add`) — 이 PC에 설치되어 있지 않다.
10. 등록 후 로그인을 순서대로 실행하는 `--login` 옵션(pi mcp login, codex mcp login 등) 추가.
11. `services list`에서 한글 이름 폭 정렬이 어긋난다.
12. 이전 보류 항목: Ludyte 텍스트→영상 레인(갭 6), 다른 세션의 jobs.py 변경 병합 후 진행. 이번 브랜치도 jobs.py 대사 도구 구간을 바꿨으므로 병합 시 충돌 확인 필요.
