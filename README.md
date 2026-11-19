<div align="center">

# 🎬 CineForge

**요구사항 한 번, 선택 한 번. 그다음은 논스톱.**
콘셉트 조합부터 기획안·SSOT·에셋·검수·생성 인계까지 이어 주는 대화형 AI 영상 제작 오케스트레이터 CLI

![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![Version](https://img.shields.io/badge/version-0.1.0-6E56CF)
![Tests](https://img.shields.io/badge/tests-51%20passed%20%C2%B7%202%20live%20opt--in-2EA44F)
![Decision](https://img.shields.io/badge/decision-Jev%201.14%20(OpenRouter)-0A7AFF)
![Generation](https://img.shields.io/badge/plan%20writer-GPT--6.2%20Sol-111111)
![Skills](https://img.shields.io/badge/skills-contents--production--skills%202.61-F97316)

</div>

---

## 소개

CineForge는 AI 에이전트(Claude Code·Codex 등)와 함께 쓰는 영상 제작 CLI입니다.

1. 만들고 싶은 영상을 자유롭게 적습니다.
2. CineForge가 **9가지 판단 요소**(대본·시나리오·레퍼런스·플롯/콘셉트·주연 캐릭터·목소리·콘텐츠 콘셉트·스토리 전개·연출)를 판정하고, 요청문에 없는 것만 **처음에 한 번** 묻습니다.
3. 선택이 끝나면 콘셉트 평가 → 기획안 → 검수 → 스토리·캐릭터·세계관 SSOT → 스토리보드 → 에셋·프롬프트·사운드 큐 시트 → 검수까지 멈추지 않고 진행합니다.
4. 비용이 드는 생성·편집 단계는 사용자가 권한(`grant`)을 준 뒤에만 [contents-production-skills](https://github.com/DeclanJeon/contents-production-skills)의 담당 스킬로 넘깁니다.

판단(요소 판정·추천·채점)은 OpenRouter의 **Jev 1.14**가, 기획안 문장은 **GPT-6.2 Sol**이 씁니다. 키가 없으면 **호스트 AI**나 오프라인 규칙이 같은 형식으로 대신합니다.

## 파이프라인

```mermaid
flowchart LR
  REQ([요구사항]) --> S00[S00 접수·분석<br/>9개 판단 요소]
  S00 --> S01[S01 콘셉트 선택<br/>처음 한 번]
  S01 --> S02[S02 조합·적합성·평가]
  S02 --> S03[S03 제작 기획안]
  S03 --> G1{G1 기획안 검수}
  G1 --> S04[S04 대본·스토리 SSOT]
  S04 --> S05[S05 캐릭터·세계관 SSOT]
  S05 --> S06[S06 연출·스토리보드·타이밍]
  S06 --> S07[S07 에셋·프롬프트·사운드 큐]
  S07 --> G2{G2 프리프로덕션 검수<br/>연속성·제약·권리}
  G2 --> GRANT[/grant execution<br/>비용 한도/]
  GRANT --> S08[S08 생성 → 스킬 인계]
  S08 --> S09[S09 편집·사운드·합성]
  S09 --> S10[S10 품질 검수]
  S10 --> G3{G3 사용자 최종 검수}
  G3 --> S11[S11 출력·이력]
  S11 -.-> S12[S12 성과 피드백<br/>설계 단계]
```

## 주요 기능

| | 기능 | 내용 |
|---|---|---|
| 🧭 | 한 번에 끝나는 선택 | 요청문에서 감지된 항목은 묻지 않고, `?`=추천, `!`=나머지 맡기기. `--non-interactive`면 남은 필수 항목을 AI 추천으로 채움 |
| 📚 | 콘셉트 라이브러리 | 18개 축, 377개 항목(형식 12대분류, 장르, 연출, 서사 12구조, 감정 등). `cineforge taxonomy`로 조회 |
| 🧪 | 조합·적합성·평가 | 적합성 규칙 16개, 연출 규칙 팩 14개, 6개 기준 점수(hook·feasibility·emotion·originality·coherence·platform_fit)와 대안 비교 |
| 📝 | 제작 기획안 | 7섹션 기획안(`plan.json`/`plan.md`), 씬·컷·타임라인 |
| 🗂️ | SSOT 8종 | 스토리·캐릭터·세계관·씬·카메라·모션·오디오·콘셉트. 해시 기반 버전·잠금·변경 영향 분석(`impact`, `lock`) |
| 🎨 | 에셋 패키지 | 등장인물·의상·소품·배경, 컷별 시작/끝 프레임, 이미지·영상 생성 프롬프트, 사운드 큐 시트 |
| ✅ | 검수 게이트 | G1 기획안, G2 연속성(CQ01–CQ11)·제약·권리(RS01–RS04), G3 사용자 최종 검수 |
| 📊 | 진행 표시 | 진행률·작업률 막대, 단계별 상태·작업 수·검수 결과·담당 스킬 |
| 🤝 | 스킬 인계 | 단계마다 담당 스킬을 지정한 인계 패킷(`handoffs/*.json`), 증거 파일로만 `complete` |

## 터미널 화면과 에이전트 진행 공유

`cineforge status`는 로고·단계 표·진행률·작업률·다음 행동·멈춤 사유를 보여 줍니다. 색은 TTY에서만 쓰고 `NO_COLOR=1`이나 리다이렉트에서는 같은 정보를 서식 없이 냅니다. `--json`은 화면 장식 없이 `schema_version: 1` 스냅샷만 출력합니다.

`cineforge new`·`run`·`status`는 같은 스냅샷을 `agent_io/progress.json`에 원자적으로 씁니다. 다른 AI 에이전트·감독 프로세스는 이 파일 하나로 현재 단계, 단계별 완료/전체 작업, 검수 상태, 다음 행동, 멈춤 사유를 읽습니다. 별도 상태 원장을 만들지 않으며 `progress.json`이 여전히 정본입니다.

### 사운드 레이어 결정표

사운드 설계는 S04 대본·S06 콘티와 같은 `plan.json`에서 계산되어 `script.md`, `ssot/scene.json`의 컷 `sound`, `ssot/audio.json`, `assets/sound_plan.json`이 같은 값을 공유합니다. 화면마다 다음 우선순위로 한 겹을 고릅니다.

| 순간 | 쓰는 것 | 담당 | 규칙 |
|---|---|---|---|
| 오프닝 훅·엔딩 | **OST(주제가)** | Suno, 보컬 | 씬 하나에 한 번, 최대 12초. 같은 선율을 엔딩에서 회수. 무대사 작품은 같은 곡을 연주 버전으로 |
| 대사 아래 | **BGM 언더스코어** | Suno, 무보컬 | OST와 같은 구간에 겹치지 않음. 대사 구간 -20 dB |
| 장소 전환·호흡 | **공간음(AMBIENCE)** | ElevenLabs | 씬 전체에 깔되 -28 LUFS, 루프 |
| 행동·소품·타격 | **효과음(SFX)** | ElevenLabs | 컷의 `sound`가 동작을 지시할 때만 단발 |
| 인물의 말 | **대사(DIALOGUE)** | Fish Audio(TypeCast 대체) | 무대사 제약이면 생성하지 않음 |
| 의도적 정적 | **무음** | — | 감정 전환·반전 직전. 다른 레이어를 끄고 만든다 |

OST는 "노래 한 곡"이 아니라 **드라마 주제의 회수 장치**입니다. 그래서 `music_themes`에 주제가와 언더스코어를 분리해 두고, 큐에는 `role`·`vocal`을 기록합니다. BGM을 OST로, OST를 BGM으로 바꿔 부르지 않습니다.

## 생성 이후 — 검수된 납품까지

S07 이후를 CLI 한 번씩 이어 붙인다. 각 단계는 파일로 남고, 실패는 다음 단계로 넘어가지 않는다.

```bash
cineforge execute <project> --stage S08_audio   # OST/BGM/SFX/대사 job 봉투
cineforge results <project> --stage S08_audio --file results.json
cineforge execute <project> --stage S08_video   # 컷별 영상 job 봉투
cineforge edit <project>                        # 결정적 편집 계획
cineforge render <project>                      # ffmpeg 조립 + 음량 정규화
cineforge verify <project> --all                # 사람 확인 후 verified 승격
cineforge gate <project>                        # verified 게이트
cineforge qa-final <project>                    # 해시·길이·스트림·음량·자막 검수
cineforge deliver <project>                     # final/<project>.mp4 + .srt + delivery.json
```

- 영수증은 입력·출력 SHA-256을 남기고, 불명 작업은 자동 재시도하지 않는다.
- `deliver`는 게이트와 최종 검수를 모두 통과할 때만 파일을 만든다. 하나라도 실패하면 기존 납품을 보존한다.
- `edit/proxy.json`에 `{"width":540,"height":960}`을 두면 프록시 해상도로 렌더한다. 검수는 실제 렌더 크기를 기준으로 한다.
- 실제 provider 호출은 `execution` 승인과 키가 있어야 하며, 이 저장소의 테스트는 로컬 ffmpeg와 가짜 실행기만 쓴다.

## 흡수한 검증 기능 (SceneWeaver)

- `cineforge qa-playback <project> --file report.json`: 납품 파일 해시에 묶인 **사람 재생 검수 기록**. `reviewer_reported`로만 남고 게이트·승인을 바꾸지 않는다.
- `cineforge skills`: 설치된 스킬팩의 실행 도구 8개를 찾아 해시를 확인한다. `deliver`는 이 핀을 `delivery.json.skills`에 기록한다.
- 전체 대기·복구·영수증 규칙은 [제작 완결 설계](docs/superpowers/specs/2026-11-20-production-closure-design.md)를 따른다.

## 사운드 디자인과 MCP

S07은 `assets/sound_plan.json`을 씁니다. 큐마다 담당 MCP·도구·프롬프트·루프·AI 표시가 붙습니다: BGM은 Suno(`suno_generate`), 효과음·공간음은 ElevenLabs(`elevenlabs_sound_effect`), 대사는 Fish Audio(`fish_audio_tts`, TypeCast 대체)입니다. 이 파일은 생성 인계이며 음원 생성 자체는 아직 실행하지 않습니다.

```bash
cineforge setup                                   # 네 서버 준비 상태 확인
cineforge setup --apply suno --recipe "suno=npx -y <suno-mcp-package>" --yes
cineforge setup --set-key elevenlabs              # 숨김 입력
cineforge setup --remove-key suno
```

키는 `~/.config/cineforge/credentials.json`(0600)에만 저장하고 프로젝트·프롬프트·로그에 남기지 않습니다. 설치는 `--yes`와 서버별 실제 설치 명령(`--recipe`)이 모두 있어야 실행하며, 명령을 모르면 추측해서 만들지 않고 거부합니다. MCP 도구가 Pi/Codex 세션에 실제로 노출되는지는 호스트 설정이 결정합니다.

## 이미지 자동 제작 (Linux)

새 프로젝트는 기본 논스톱입니다. 수동 검토는 `--no-nonstop`. 기획을 먼저 실행한 뒤 `cineforge run <project> --image-limit N`으로 작품 누적 이미지 호출 수와 참조 전송을 승인하거나, 처음부터 `new`에 같은 옵션을 줍니다. N은 동시 실행 수가 아닙니다(동시 실행 최대 5). 스킬 정책상 Codex Imagen 정지 이미지는 유료 견적·비용 상한 대상이 아니므로, 이 값은 실행 범위와 참조 전송 범위를 제한하는 장치입니다. 비용·원격 작업이 불확실하면 자동 재제출하지 않습니다.

```mermaid
flowchart TD
  A[영상 요청] --> B[기획 · 대본 · 캐릭터 · 컷 구성]
  B --> C[연속성 · 권리 · 제약 검사]
  C --> D[이미지 목록과 참조 관계 작성]
  D --> E{사용 가능한 이미지인가?}
  E -->|등록된 자료 또는 동일 해시 결과| F[재사용]
  E -->|없음| G{실행 범위 --image-limit 지정?}
  G -->|예| H[Codex Imagen 독립 세션 최대 5개]
  G -->|아니오| I[작업 수 안내 · 승인 대기]
  H --> J[결과 경로와 해시 기록]
  F --> K[참조 준비된 컷의 시작·끝 프레임]
  J --> K
  K --> L[영상·음성 생성 담당에 인계]
  L --> M[외부 실행 결과 수신 → 편집 · QA · 최종 검수]
```

제공 이미지는 프로젝트 아래에 두고 `assets/supplied_images.json`에 `{"프롬프트ID":"상대경로"}`로 명시합니다. 큐는 감독 CLI가 떠 있는 동안 독립 프로세스 세션으로 실행되며 GUI 창이나 상시 데몬이 아닙니다. 산출물 목록은 `assets/image_outputs.json`, 작업별 기록은 `assets/image_jobs/`입니다. 영상·음성·편집은 기존 외부 인계이며 이 큐가 대신 실행하지 않습니다.

## 빠른 시작

### 설치

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cineforge --version   # cineforge 0.1.0
```

### 대화형

```bash
cineforge new "60초 코미디 숏드라마, 연출은 시네마틱 실사, 서사는 결말 선공개"
```

### 비대화형 + 논스톱

```bash
# 질문 없이 진행하고, 기획안·프리프로덕션 승인을 미리 위임(생성 비용 권한은 별도)
cineforge new "60초 코미디 숏드라마, 연출은 시네마틱 실사, 서사는 결말 선공개" \
  --non-interactive --nonstop --set aspect=9:16

# 생성 단계 앞에서 멈추면, 비용 한도와 함께 실행 권한을 기록하고 이어서 실행
cineforge grant productions/<id> execution --spend-ceiling 20USD
cineforge run productions/<id>

# 스킬이 생성을 마치면 증거 파일과 함께 완료 기록
cineforge complete productions/<id> S08_generation --evidence renders/*.mp4
```

### 그 밖의 명령

| 명령 | 하는 일 |
|---|---|
| `status <프로젝트>` | 진행률·작업률·검수 상태 |
| `accept <프로젝트> plan\|preproduction\|final` | 게이트 승인 |
| `select <프로젝트>` | 콘셉트 선택 다시 하기 |
| `impact <프로젝트> <ssot>` / `lock <프로젝트> <ssot>` | SSOT 변경 영향 분석(`--apply`) / 잠금(`--unlock`으로 해제) |
| `analyze "<요청>"` | 요구사항 분석만(JSON) |
| `providers` | 판단·생성 공급자 체인과 사용 가능 여부 |
| `taxonomy [--axis narrative]` | 콘셉트 라이브러리 보기·내보내기 |

## 진행 표시 예시

아래는 `--provider mock`(네트워크 없음)으로 위 비대화형 예시를 실제로 실행하고 `grant` 후 `run`한 출력입니다(위쪽 줄 일부 생략).

```text
프로젝트 20261120-001809-60초-코미디-숏드라마-연출은-시네마틱-실사 — 현재 단계: S08_generation
진행률 ███████████████░░░░░░░░░  62.6%   (단계 가중치 기준)
작업률 ██████████████████░░░░░░  73.2%   (완료 작업 / 전체 작업)

단계                        상태                 작업  검수    담당 스킬
S00 요구사항 접수·분석            ✅ done            3/3    -     creative-production
S01 콘셉트 선택(대화형)           ✅ done            3/3    -     concept-intake-design
S02 콘셉트 조합·적합성·평가         ✅ done            4/4    PASS  concept-intake-design
S03 제작 기획안                ✅ done            7/7    PASS  developing-video-synopses, orchestrating-video-preproduction
G1  기획안 검수 게이트            ✅ done            2/2    PASS  creative-production
S04 대본·스토리 SSOT           ✅ done            3/3    -     developing-video-synopses, video-production-assets
S05 캐릭터·세계관 SSOT          ✅ done            6/6    -     designing-video-character-sheets, designing-character-personas
S06 연출·스토리보드·타이밍          ✅ done            4/4    -     storyboarding-video, camera-spatial-design, animatic-direction, silent-visual-storytelling
S07 에셋·프롬프트·사운드 큐 시트      ✅ done            5/5    -     video-production-assets, ai-camera-control, creative-production
G2  프리프로덕션 검수(연속성·제약·권리)  ✅ done            4/4    PASS  video-production-assets
S08 이미지·영상·음성 생성          🔌 waiting_exter   0/4    -     higgsfield-generate, creative-production
    └ 호스트 에이전트가 higgsfield-generate, creative-production로 실행 → 완료 후 `cineforge complete`
S09 편집·사운드·합성             · pending         0/4    -     video-production-assets
S10 품질 검수                 · pending         0/4    -     video-production-assets, creative-production
G3  사용자 최종 검수             · pending         0/1    -     creative-production
S11 최종 출력·이력              · pending         0/2    -     recording-production-history
S12 성과 피드백                ⤼ skipped         0/2    -     topic-demand-selection, searching-social-media
    └ 성과 피드백(L6)은 로드맵 6단계 — 현재 설계만

조합된 제작 콘셉트: 60초 코미디 숏드라마 — 시네마틱 실사 연출 · 결말 선공개 서사
  코미디 × 시네마틱 × 결말 선공개형 | 감정: 공감 → 감동
  평가: 76.0점 (go) hook=90 feasibility=50 emotion=90 originality=50 coherence=90 platform_fit=90
  대안: 서사 → 미스터리 회수형 → 76.0점
  대안: 서사 → 카운트다운형 → 80.0점
```

`grant` 전에는 S08이 `⛔ blocked`로 멈추고 "'execution' 권한 필요" 안내가 나옵니다.

## 공급자와 모델

| 역할 | 기본 | 모델 / 경로 | 가격(100만 토큰당) |
|---|---|---|---|
| 판단(요소 판정·추천·채점) | Jev 1.14 via OpenRouter | `typesafe/jev-1.14` · `POST /api/alpha/decisions` | 입력 $0.042 · 출력 무료 |
| 판단(대체) | Jev 1.14 직접 | TypeSafe `POST /v1/systemone` · `jev-1.14.0` | TypeSafe 요금 |
| 기획안 작성(생성) | **GPT-6.2 Sol** via OpenRouter | `openai/gpt-6.2-sol` · `POST /api/v1/chat/completions` | 입력 $2 · 출력 $10 |
| 키가 없을 때 | 호스트 AI / 규칙 / 목 | `agent_io/` 요청·응답 파일, `heuristic`, `mock` | 무료 |

- 실패하면 다음 공급자로 넘어가고 `provider_log.json`에 이유를 남깁니다.
- 모드: `--provider auto`(기본) · `host` · `openrouter` · `mock`.
- 60초 기획안 1편 예상 비용은 약 $0.07, Jev 판단 1회는 약 $0.00002입니다.

## 환경변수

| 변수 | 용도 |
|---|---|
| `OPENROUTER_API_KEY` | Jev 1.14 판단과 기획안 생성. **이 키를 넣는 것이 유료 호출의 opt-in**이며, 없으면 어떤 유료 호출도 하지 않음 |
| `TYPESAFE_API_KEY` | Jev 1.14 판단(TypeSafe 직접 API) |
| `CINEFORGE_GEN_MODEL` | 기획안 생성 모델 slug. 기본값 `openai/gpt-6.2-sol`(ADR-010). 다른 slug로 덮어쓰기, `off`면 생성 끔 |
| `CINEFORGE_AGENT_MODE=1` | auto 모드에서도 호스트 AI에게 판단·생성을 맡김 |
| `CINEFORGE_LIVE=1` | 실호출 테스트(`tests/test_live_openrouter.py`) 켜기 |

키는 환경변수로만 받고 파일·로그·명령 인자에 남기지 않습니다.

### 로컬 검증·복구 (SceneWeaver 이식)

- 외부 작업 대기 상태에서만 최초 완료를 기록합니다. `--evidence`에는 프로젝트 내부 실제 파일을 지정하세요. 목록 파일을 지정하면 목록 자체만 검증하므로 원본 테이크/편집본도 각각 명시해야 합니다.
- 완료 시 입력·출력 SHA-256을 `receipts/<단계>.json`에 먼저 저장합니다. 상태 기록 전 중단됐다면 `cineforge run`으로 복구합니다. 해시 불일치 또는 기존 완료 단계에 영수증이 없으면 자동 인정하지 않습니다. 영수증은 시청 판정이나 원격 작업 접수증이 아닙니다.
- 출연진은 프로젝트마다 지정합니다. `--with-dialogue`와 `--no-speech`는 인물 이름과 무관한 작품별 옵션입니다.
- Pi 서명 모드는 선택 사항입니다. 실행기와 Pi 서명 프로세스에만 프로젝트 밖의 32바이트 이상 비밀 파일 경로 `CINEFORGE_HOST_KEY_FILE`을 지정하세요. `--provider host`로 요청한 뒤 같은 환경에서 `python -m cineforge.host_sign REQUEST.json BODY.json`으로 응답을 작성하고 `cineforge run`으로 이어갑니다. 비밀 파일을 저장소나 프롬프트에 넣지 마세요. 기존 무서명 모드는 호환용이며 서명된 요청에 대체 사용할 수 없습니다. 제안은 실행 권한이 아닙니다.

### 호스트 AI 모드

`--provider host`이면 CineForge가 `agent_io/requests/*.json`에 질문을 쓰고 멈춥니다. 에이전트가 `agent_io/responses/*.json`에 같은 형식으로 답을 쓰면 `cineforge run`으로 이어집니다.

## 스킬 연동

CineForge는 [contents-production-skills](https://github.com/DeclanJeon/contents-production-skills)(2.61, 브랜치 `feat/orchestration`)와 짝을 이룹니다.

- **`concept-intake-design`**: 9개 판단 요소를 한 번에 묻고, 콘셉트를 조합·검사·평가해 콘셉트 패킷으로 넘기는 새 스킬입니다. 분류 체계와 규칙은 `cineforge taxonomy --export … --with-rules`로 동기화합니다.
- **라우팅 R33**: `creative-production` 2.4의 Step 0 사전 인테이크가 R33으로 이 스킬을 부릅니다.
- **`creative-production/references/skill-map.md`**: 단계별 담당 스킬, 논스톱 규칙, CineForge 인계 계약을 정리한 문서입니다.
- **인계 패킷**: 단계마다 `handoffs/<단계>.json`에 담당 스킬·입력·권한·비용 한도를 담습니다. 실제 이미지·영상 생성과 편집은 스킬이 실행하고(ADR-005), CineForge는 증거 파일로 완료를 기록합니다.

## 안전·비용 원칙

- CineForge는 유료 이미지·영상 생성 API를 직접 부르지 않습니다. 생성은 `grant execution --spend-ceiling`으로 한도를 정한 뒤 스킬이 실행합니다.
- 테스트와 기본 실행은 네트워크를 쓰지 않습니다. 실호출 테스트는 `CINEFORGE_LIVE=1`일 때만 돕니다.
- 레퍼런스·드라마 각색은 구조·리듬·장르 문법만 참고합니다. 원본 영상·음악·대사는 재사용하지 않고, 원작 캐릭터도 복제하지 않습니다.
- AI 생성 콘텐츠는 게시할 때 플랫폼의 AI 표시 기능과 해시태그로 공개합니다. 영상 안에 'Made with AI' 코너 라벨은 넣지 않습니다.
- AI 페르소나 콘텐츠는 AI임을 숨기지 않습니다. 이 표시 규칙은 대사 유무와 별개입니다.
- 게시·전송·결제·OAuth·푸시 같은 외부 행동은 CineForge 범위 밖이며, 사용자 승인 없이는 하지 않습니다.

## 로드맵

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 콘셉트 라이브러리+조합·평가 | ✅ 구현(v0.1.0) |
| 2 | 스토리·캐릭터·세계관+SSOT | ✅ 규칙 기반 구현 |
| 3 | 연출·스토리보드·타이밍 | ✅ 규칙 기반 구현 |
| 4 | 프롬프트·모델 라우팅·생성 | 🟡 프롬프트·큐 시트·인계 구현, 생성은 스킬 담당 |
| 5 | 편집·연속성 검수 | 🟡 연속성 규칙·G2 구현, 편집 실행은 설계 |
| 6 | 성과 분석·자동 개선 | ⏳ 설계 |

자세한 마일스톤은 [docs/14-roadmap.md](docs/14-roadmap.md)에 있습니다.

## 프로젝트 구조

```text
cineforge/
├── cineforge/                 패키지
│   ├── cli.py                 명령(new·select·run·status·accept·grant·complete·impact·lock·providers·analyze·taxonomy)
│   ├── pipeline.py            단계 실행·상태 기계·게이트
│   ├── intake.py              9개 판단 요소 분석
│   ├── selection.py           한 번에 끝나는 콘셉트 선택
│   ├── concept.py             조합·적합성·평가
│   ├── planner.py, render.py  기획안 생성·렌더
│   ├── ssot.py                SSOT 8종 버전·잠금·영향 분석
│   ├── assets.py              에셋·프레임·프롬프트·사운드 큐 시트
│   ├── qa.py, progress.py     검수 규칙, 진행 표시
│   ├── providers/             jev(OpenRouter·TypeSafe), openrouter-gen, host-agent, heuristic, mock, router
│   └── data/                  taxonomy.yaml, rules.yaml, pipeline.yaml, schemas/(19개)
├── templates/                 기획안·캐릭터 바이블·에셋·프롬프트·사운드 큐 시트
├── examples/plans/            《면접관이 제 전 여친입니다》 60초 예시 기획안
├── docs/                      설계 문서 00–19, adr/
└── tests/                     pytest(오프라인 51개 + 실호출 opt-in 2개)
```

제작 결과는 `productions/<id>/` 아래에 `intake.json`, `selection.json`, `concept.json`, `plan.json`/`plan.md`, `ssot/`, `assets/`, `handoffs/`, `reviews/`, `progress.json`, `provider_log.json`으로 쌓입니다.

## 문서

| 문서 | 내용 |
|---|---|
| [00 색인](docs/00-index.md) | 전체 문서 안내 |
| [01 요구사항 명세(SRS)](docs/01-srs.md) | 기능·비기능 요구사항, 인수 기준 |
| [02 아키텍처](docs/02-architecture.md) | 구성 요소와 데이터 흐름 |
| [03 콘셉트 분류 체계](docs/03-concept-taxonomy.md) · [04 콘셉트 엔진](docs/04-concept-engine.md) | 분류 목록, 조합·평가 |
| [05 상태 기계·스킬 라우팅](docs/05-orchestration-state-machine.md) · [07 단계 계약](docs/07-pipeline-contracts.md) | 단계 전이, 입력·출력·권한 |
| [06 SSOT 데이터 모델](docs/06-ssot-data-model.md) | 8종 SSOT, 버전·잠금 |
| [08 CLI UX](docs/08-cli-ux.md) · [09 진행·검수 보고](docs/09-progress-qa-reporting.md) | 명령과 화면 |
| [10 LLM 공급자 라우팅](docs/10-llm-provider-routing.md) | Jev 요청 형식, 폴백 체인, 호스트 프로토콜 |
| [11 템플릿](docs/11-templates.md) · [12 연속성·검수 규칙](docs/12-continuity-qa-rules.md) | 템플릿, 검수 규칙 |
| [13 비용·권리·안전](docs/13-cost-rights-safety.md) | 권한·비용·권리·AI 표기 |
| [14 로드맵](docs/14-roadmap.md) · [15 테스트 계획](docs/15-test-plan.md) | 일정, 테스트 범위 |
| [17 스킬 업그레이드 계획](docs/17-skills-upgrade-plan.md) · [18 레퍼런스 조사](docs/18-reference-study.md) · [19 엔진 카탈로그](docs/19-engine-catalog.md) | 스킬 2.61, 참고 프로젝트, 엔진 16개 |
| [ADR 목록](docs/adr/README.md) | 설계 결정 001–010 |

## 테스트

```bash
python -m pytest -q                       # 오프라인 51개 통과, 실호출 2개 건너뜀
CINEFORGE_LIVE=1 python -m pytest -q tests/test_live_openrouter.py   # 키 필요, 소액 과금
```
