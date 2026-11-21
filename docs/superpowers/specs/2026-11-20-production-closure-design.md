# 제작 완결(Production Closure) 설계 — 요청에서 완성 MP4까지

- 상태: 제안(v1), 2026-11-20
- 대상: CineForge CLI (`/home/declan/Documents/Projects/Products/01_Persnal_Work/cineforge`)
- 관련: [SRS](../01-srs.md), [파이프라인 계약](../07-pipeline-contracts.md), [비용·권리·안전](../13-cost-rights-safety.md)

## 1. 문제

현재 CineForge는 **S07까지** 실제로 만든다. 기획·SSOT·에셋 프롬프트·이미지 생성·사운드 설계는 동작하고 테스트로 고정돼 있다. 그러나 S08의 영상·음성, S09 편집, S10 결과 검수, S11 납품은 인계 패킷만 남기고 끝난다. 그래서 "영상 하나 만들어줘"가 **MP4로 끝나지 않는다.**

## 2. 목표와 비목표

**목표**
1. 승인된 범위 안에서 이미지·음성·영상 작업을 **호스트 실행기**에 넘기고, 결과를 **영수증으로 회수**한다.
2. 회수된 테이크를 **결정적 편집 계획**으로 조립해 H.264/AAC MP4를 만든다. 음량 정규화와 자막을 포함한다.
3. 완성 파일을 **해시·길이·스트림·음량·자막 정렬**로 검수하고, 실패하면 납품하지 않는다.
4. `available`과 `verified`를 분리하고, **verified 게이트**가 최종 납품을 막는다.
5. 위 과정을 CLI 한 번의 실행과 재개로 이어 붙인다.

**비목표**
- 공급자 API 키를 CLI가 직접 보관·호출하지 않는다(호스트·MCP가 실행).
- 생성 모델의 미학적 품질을 보장하지 않는다. 검수는 기술·연속성·계약 기준이다.
- 게시·업로드·결제 자동화는 범위 밖이다(승인 후에도 별도).
- 렌더 팜·분산 스케줄러·클라우드 스토리지는 만들지 않는다.

## 3. 아키텍처

```text
S07 산출물(프롬프트·큐·SSOT)
        │
        ▼
[작업 생성] jobs.py  ── 결정적 job_id·idempotency_key·입력 핀
        │  jobs/<stage>.json  (호스트 실행용 봉투)
        ▼
호스트 실행기(MCP: codex-imagen / suno / elevenlabs / fish_audio / ludyte)
        │  결과 파일 + 실행 메타데이터
        ▼
[결과 회수] receipts.py  ── 경로·SHA-256·provider·model 기록, 불명=보류
        │
        ├─ 이미지: asset_registry available → (사람/QA) verified
        ├─ 음성: audio_registry cue별 파일·해시
        └─ 영상: take_registry cut별 채택 테이크
        ▼
[편집] edit_plan.py → assembly.py (ffmpeg) ── 컷 조립·음성 믹스·자막·라우드니스
        ▼
[최종 검수] final_qa.py ── 해시·길이·스트림·음량·자막·게이트
        ▼
[납품] final/<slug>.mp4 + .srt + delivery.json
```

### 3.1 실행 경계

- CineForge는 **작업 봉투(envelope)** 를 쓰고 멈춘다. 실행은 호스트 에이전트(또는 사용자가 지정한 실행기)가 한다.
- 봉투는 `schema_version`, `project_root`, `stage`, `jobs[]`, `authority`(실행 승인·비용 상한·허용 provider), `binding`(project.json+authority+SSOT 해시)을 담는다.
- 각 job은 `job_id`, `kind`, `provider`, `tool`, `inputs`(경로→해시), `params`, `idempotency_key`, `depends_on`을 가진다.
- **비밀은 봉투에 넣지 않는다.** 키는 `~/.config/cineforge/credentials.json`(0600) 또는 호스트 환경에만 둔다.

### 3.2 상태 기계

```text
planned → authorized → submitted → accepted
                         └→ rejected   (재시도 금지, 원인 기록)
                         └→ uncertain  (자동 재제출 금지, 사람 확인)
accepted → verified (QA 통과) | stale (입력 변경)
```

- `uncertain`은 **자동 재시도하지 않는다.** 파일이 일부 있으면 해시를 확인해 채택 여부를 사람이 정한다.
- 입력 핀이 바뀌면 하위 작업은 `stale`. 상위만 조용히 갱신하지 않는다.

### 3.3 공급자 레인

| 자산 | 기본 실행기 | MCP 도구 | 승인 |
|---|---|---|---|
| 스틸 | codex-imagen | `image_generation` | 실행 범위 상한(`--image-limit`) |
| OST/BGM | Suno 공식 원격 MCP | 연결 후 확정 (`https://api.suno.com/mcp`, OAuth) | `execution` + 작품 예산 |
| 효과음/공간음 | ElevenLabs | `elevenlabs_sound_effect` | `execution` |
| 대사/보이스 | Fish Audio (TypeCast 대체) | `fish_audio_tts` | `execution` + 목소리 승인 |
| 컷 영상 | Ludyte | `create_session`/`send_message` | `execution` + 모델·길이 확정 |

- provider는 **명시 선택**한다. 실패 시 다른 공급자로 조용히 넘어가지 않는다.
- Codex Imagen 정지 이미지는 유료 견적 대상이 아니지만, 참조 전송·출력 범위는 승인 범위 안이어야 한다.

## 4. 데이터 계약

| 파일 | 역할 | 필수 필드 |
|---|---|---|
| `jobs/<stage>.json` | 실행 봉투 | schema_version, binding, authority, jobs[job_id, kind, provider, tool, inputs, params, idempotency_key, depends_on] |
| `receipts/<stage>.json` | 회수 영수증 | schema_version, binding, results[job_id, status, path?, sha256?, error?, provider_meta?] |
| `assets/asset_registry.json` | 스틸 | 기존 + `status(verified)`, `sha256`, `version` |
| `audio/audio_registry.json` | 음성 | cue_id, path, sha256, duration, provider, status |
| `takes/take_registry.json` | 컷 테이크 | cut_id, take_id, path, sha256, duration, status |
| `edit/edit_plan.json` | 편집 계획 | cuts[cut_id, take, in, out, transition], audio[cue, path, gain], subtitles[{in,out,text}] |
| `qa/final_report.json` | 최종 검수 | status, checks[], video/audio probe, loudness, hash |
| `final/delivery.json` | 납품 | mp4 path/hash, srt, duration, aspect, fonts, gate evidence |

새 원장은 만들지 않는다. 위 파일은 모두 `project.json`·SSOT에서 파생된 투영이며, 승인 상태는 기존 `authority.json`이 정본이다.

## 5. 편집·믹스 규칙

- 컷 순서·길이는 `ssot/scene.json`과 테이크 실길이의 **교집합**으로 정한다. 테이크가 짧으면 실패하고 늘리지 않는다.
- 오디오는 `sound_plan`의 큐를 타임라인에 배치한다: OST/BGM/공간음/효과음/대사. 타격 구간의 음악 공백은 이미 설계에 있다.
- 라우드니스: 통합 **-14 LUFS**(±1), true peak **-1 dBTP** 이하. 측정은 ffmpeg `loudnorm` 2-pass.
- 자막: 대사 큐 → SRT(UTF-8). 기본은 사이드카, `--burn`일 때만 영상에 굽는다. 줄 길이·최소 표시 시간(1.2s) 검사.
- 인코딩: H.264 yuv420p, AAC 48kHz, 24fps(프로젝트 fps), `+faststart`.
- 결정성: 같은 입력·같은 테이크·같은 계획이면 같은 편집 계획 JSON이 나온다(타임스탬프 제외).

## 6. 최종 검수 (fail-closed)

| 검사 | 기준 |
|---|---|
| 파일 | 존재, 크기>0, `final/` 경로 |
| 해시 | `delivery.json`과 실제 SHA-256 일치 |
| 길이 | 목표 러닝타임 ±0.2s |
| 스트림 | H.264 + AAC, 해상도·fps 일치 |
| 디코드 | 전체 디코드 오류 0 |
| 음량 | -14 LUFS ±1, TP ≤ -1 dBTP |
| 자막 | 각 큐 in/out이 영상 범위 안, 겹침·공백 규칙 |
| 게이트 | 관련 자산·테이크가 모두 `verified`, 핀 최신 |
| 권리 | RS 규칙 위반 0, AI 표시 정보 존재 |

하나라도 실패하면 `final_report.status=fail`, 납품 파일을 만들지 않는다.

## 7. 재개·불명 처리

- 실행 전 중단: `planned` 유지, 재실행 시 같은 봉투(동일 idempotency_key).
- 제출 후 중단: `uncertain`으로 남기고 자동 재제출 금지. `cineforge resolve <job> --accept PATH` 또는 `--reject`로만 전이.
- 회수 후 편집 전 중단: 영수증이 있으면 편집만 재실행.
- 편집 후 검수 전 중단: `final_report`가 없으면 검수부터. 있으면 해시 확인 후 납품만.
- 입력 변경: 하위 job·테이크·편집 계획·검수를 `stale`로 표시하고 이유를 남긴다.

## 8. 권한·보안

- `execution` 승인 없이는 어떤 유료/외부 생성 job도 `authorized`가 되지 않는다.
- `spend_ceiling`이 있으면 예상 비용 합이 이를 넘을 때 봉투를 만들지 않는다.
- provider 허용 목록 밖 요청은 거부한다. 실패를 다른 provider로 대체하지 않는다.
- 경로 탈출·심볼릭 링크·프로젝트 밖 출력은 거부한다.
- 영수증·로그·봉투에 키를 쓰지 않는다. 테스트는 가짜 키만 쓴다.
- AI 생성 표시는 납품 메타데이터에 남기고, 게시 시 플랫폼 표시 의무를 사용자에게 알린다.

## 9. 테스트 전략

1. **단위**: job 생성 결정성, idempotency, 상태 전이, 핀 변경 시 stale, 게이트 차단.
2. **계약**: 봉투·영수증 스키마(JSON Schema)와 실제 파일.
3. **통합(로컬)**: 가짜 실행기로 이미지·음성·영상 파일을 만들고, ffmpeg로 실제 MP4 조립·검수. 외부 호출 0.
4. **실패 주입**: 제출 후 중단, 해시 변조, 짧은 테이크, 음량 초과, 자막 범위 초과.
5. **실제 실행**: 승인된 provider 1개로 최소 1컷 생성 → 영수증 확인. 이 항목은 비용 승인 없이는 unchecked로 둔다.

## 10. 진행률과 95% 정의

- **고정 분모 20** = 작업지시서 태스크 12 + 인수 rubric 8.
- 진행률 = 완료 태스크 + 충족 rubric / 20. **95% = 19/20**.
- 태스크는 테스트 통과와 산출물로만 완료 처리한다. rubric은 이 세션에서 명령을 실행한 증거가 있어야 체크한다.
- 실제 provider 호출이 필요한 rubric은 승인 전까지 unchecked이며, 대신 로컬 가짜 실행기 증거로 태스크를 닫는다. **95%는 “구조·검증 완결”이며 “실제 유료 렌더 완료”를 뜻하지 않는다.**

## 11. 위험

| 위험 | 완화 |
|---|---|
| MCP 도구 이름·스키마 변동 | 봉투에 도구 이름을 데이터로 두고, 실행 전 계약 확인 |
| 생성 파일이 광고 길이와 불일치 | 테이크 실길이 검사, 부족 시 실패(늘리지 않음) |
| 음량·자막 회귀 | 고정 임계값 + 샘플 fixture 회귀 테스트 |
| 비용 폭주 | execution 승인·예산·provider 허용 목록·중복 방지 |
| 부분 산출물을 완성으로 오인 | verified 게이트·fail-closed 검수·영수증 |
