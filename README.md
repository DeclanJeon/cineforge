# CineForge

요구사항을 한 번 말하고, 필요한 선택을 **처음에 한 번** 끝내면, 콘셉트 조합·적합성 검사·평가 → 제작 기획안 → 검수 → 캐릭터·세계관·스토리보드 SSOT → 에셋·시작/끝 프레임·프롬프트·사운드 큐 시트 → 검수 → (승인 시) 생성·편집·검수·출력 인계까지 이어서 진행하는 대화형 영상 제작 CLI입니다. 단계마다 [contents-production-skills](../../04_Skills/Skills-and-Automation/contents-production-skills)의 담당 스킬을 지정해 인계하고, 진행률·작업률·검수 상태를 보여줍니다.

판단(요소 판정·추천·채점)은 OpenRouter의 **Jev 1.14**(`typesafe/jev-1.14`)를 쓰고, 키가 없거나 실패하면 **호스트 AI**(이 CLI를 실행하는 에이전트)가 같은 형식으로 답합니다.

## 설치

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## 빠른 시작

```bash
# 대화형(감지된 항목은 묻지 않음, ?=추천, !=나머지 맡기기)
cineforge new "60초 코미디 숏드라마, 연출은 시네마틱 실사, 서사는 결말 선공개"

# 비대화형 + 검수 게이트 사전 위임(생성 비용 권한은 별도)
cineforge new "…" --non-interactive --nonstop --set aspect=9:16

cineforge status productions/<id>
cineforge accept productions/<id> plan
cineforge grant productions/<id> execution --spend-ceiling 20USD
cineforge complete productions/<id> S08_generation --evidence renders/*.mp4
cineforge taxonomy --axis narrative
```

## 공급자

| 환경변수 | 용도 |
|---|---|
| `OPENROUTER_API_KEY` | Jev 1.14 판단(OpenRouter Decisions API, 실호출 확인), 그리고 생성 모델. **키를 넣는 것이 유료 호출의 opt-in** |
| `TYPESAFE_API_KEY` | Jev 1.14 판단(TypeSafe 직접 API) |
| `CINEFORGE_GEN_MODEL` | 기획안 생성 모델 slug. 기본값 `openai/gpt-6.1-terra`(ADR-008), 다른 slug로 덮어쓰기, `off`면 끔 |
| `CINEFORGE_AGENT_MODE=1` | auto 모드에서도 호스트 AI에게 판단·생성을 맡김 |

`--provider host`이면 `agent_io/requests/*.json`을 에이전트가 읽고 `agent_io/responses/*.json`을 쓰면 `cineforge run`으로 이어집니다. `--provider mock`은 네트워크 없이 끝까지 시험합니다. 실호출 테스트는 `CINEFORGE_LIVE=1 python -m pytest -q tests/test_live_openrouter.py`(키 필요, 1회 약 $0.001 미만). 키는 환경변수로만 받고 파일·로그에 남기지 않습니다. CineForge는 유료 이미지·영상 생성 API를 직접 호출하지 않습니다.

## 구조

```
cineforge/            패키지(cli, pipeline, intake, selection, concept, planner, render, ssot, assets, qa, progress, providers/)
cineforge/data/       taxonomy.yaml, rules.yaml, pipeline.yaml, schemas/*.schema.json
templates/            기획안·캐릭터 바이블·에셋·프롬프트·사운드 큐 시트
examples/plans/       《면접관이 제 전 여친입니다》 예시 기획안(JSON)
docs/                 설계 문서 00–19, adr/
tests/                pytest(오프라인)
```

설계 문서는 [docs/00-index.md](docs/00-index.md)에서 시작하세요.

## 테스트

```bash
python -m pytest -q
```
