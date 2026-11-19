# 04. 콘셉트 엔진

모듈: `cineforge/concept.py`, 데이터: `cineforge/data/rules.yaml`. 엔진 E02(라이브러리)·E03(조합)·E04(평가), 계층 L1(제약·적합성).

## 1. 입력

`selection.json` — 축별 값, `direction` 하위 축, `constraints`(예: no_speech, ai_persona_disclosure), `overrides`(의도적 혼합으로 통과시킬 규칙 ID), `sources`(user/request/preset/ai).

## 2. 조합(combine)

- `title_line`: "{길이} {장르} {형식}" (예: 60초 코미디 숏드라마)
- `subtitle`: "{질감·표현} 연출 · {서사} 서사"
- `chain`: 장르 × 질감 × 서사 (+ 문화권·시대·세계관이 있으면 추가)
- `emotion_arc`: 감정 곡선 "A → B → C"
- 서사 구조의 단계 흐름(NARRATIVE_TEMPLATES 12종)을 기획안 '핵심 전략'으로 넘긴다.

## 3. 적합성 검사

`rules.yaml`의 C001–C016 + 코드 규칙 C100. 조건은 모두 참일 때 발동, 값 목록은 any-of.

| 심각도 | 처리 |
|---|---|
| error | S02를 `blocked`로. override 가능한 규칙은 `selection.overrides`에 ID를 넣으면 info로 내려간다 |
| warn | 진행, 기획안 '제작 전 확인할 사항'과 검수 보고서에 남김 |
| info | 참고 |

C100: 대사 없음 제약 + 사운드 축이 대사/내레이션 중심 → error, override 불가.

## 4. 콘셉트 → 연출 규칙 변환

`direction_rules` 팩 14개(D_kr_melo_1990s, D_joseon, D_y2k, D_near_future, D_k_drama, D_kr_makjang, D_jp_pure, D_nordic_noir, D_cn_xianxia, D_us_sitcom, D_stickman, D_live_animatic, D_comedy, D_horror). 선택이 `when`과 맞으면 규칙을 합친다(목록은 합집합, 단일 값은 먼저 맞은 팩 우선).

예: 1990년대 한국 멜로
- 소품·의상: 삐삐·공중전화·카세트 워크맨·필름 카메라, 통 넓은 청바지·니트 조끼·헤어밴드, 브라운관 TV·다이얼 전화
- 금지 소품: 스마트폰, 무선 이어폰, LED 간판, QR코드 → G2의 CQ10이 컷 묘사·프롬프트에서 검사
- 연기·대사: 존댓말·반말 전환이 감정 신호, 직설 고백보다 머뭇거림
- 색·질감: 따뜻한 황색 톤·약한 할레이션, 필름 그레인·가벼운 VHS 노이즈
- 음악·효과음: 어쿠스틱 발라드/피아노, 삐삐 수신음·동전·빗소리

## 5. 평가

6개 기준을 Score 질문(등급 10/30/50/70/90)으로 묻는다. Jev가 있으면 Jev, 없으면 호스트 AI, 그것도 없으면 규칙 기반 점수(heuristic_scores).

| 기준 | 가중치 | 규칙 기반 근거 |
|---|---|---|
| hook | .25 | 서사 구조 hook_weight, 후킹 선택 |
| feasibility | .20 | 제작 방식·카메라 ai_difficulty, 길이 대비 복잡도 |
| emotion | .15 | 감정 곡선 길이·대비 |
| originality | .15 | 흔한 조합 감점, override한 의도적 혼합 가점 |
| coherence | .15 | 적합성 경고 수 |
| platform_fit | .10 | 길이·화면비 |

판정: 합계 ≥ 65이고 차단 오류 없음 → `go`, ≥ 50 → `revise`, 그 밖 → `rework`. `candidates`는 서사 구조만 바꾼 대안 2개를 같은 방식으로 평가한다.

## 6. 출력

`concept.json`: `concept`, `compatibility`, `blocking`, `direction_rules`, `evaluation{scores,total,verdict,providers}`, `candidates`. `ssot/concept.json`은 여기서 파생된다.
