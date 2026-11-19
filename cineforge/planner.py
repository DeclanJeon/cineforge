"""S03 제작 기획안 생성 — 공급자 추상화(생성)로 기획안 JSON을 만들고 검증·사전점검한다."""
from __future__ import annotations

import json
import math
import re
from typing import Any

from cineforge.schemas import validate_with_schema, load_schema

# 서사 구조별 기본 비트(비율 합 1.0). 기획안 생성 시 구조 가이드로 쓰인다.
NARRATIVE_TEMPLATES: dict[str, list[tuple[str, float, str]]] = {
    "ending_first": [("충격적인 결말 선공개", 0.07, "결말 장면을 먼저 보여준다"), ("과거로 · 시작", 0.13, "평범한 시작"),
                     ("갈등", 0.30, "의문이 커진다"), ("증폭", 0.25, "상황이 폭주한다"), ("결말 회수 · 2차 반전", 0.25, "첫 장면의 진짜 의미")],
    "twist": [("설정", 0.2, "인물과 상황 소개"), ("전개", 0.3, "기대 형성"), ("고조", 0.3, "오해의 정점"), ("반전", 0.2, "의미가 뒤집힘")],
    "mystery_payoff": [("의문 제시", 0.15, "질문 하나"), ("단서 1", 0.25, "첫 단서"), ("단서 2", 0.3, "엇갈린 단서"), ("회수", 0.3, "의문 해결")],
    "time_loop_structure": [("루프 1", 0.25, "사건 발생"), ("루프 2", 0.25, "새 사실 1"), ("루프 3", 0.25, "새 사실 2"), ("탈출", 0.25, "루프를 깸")],
    "countdown": [("제한 제시", 0.15, "남은 시간 공개"), ("시도 1", 0.25, "실패"), ("시도 2", 0.3, "더 큰 실패"), ("마지막 순간", 0.3, "결과")],
    "escalation": [("작은 오해", 0.2, "사소한 시작"), ("확대", 0.25, "오해가 커짐"), ("폭발", 0.3, "큰 사건"), ("수습/반전", 0.25, "결말")],
    "emotional_reversal": [("코믹한 시작", 0.3, "웃음"), ("전환점", 0.2, "분위기 반전"), ("감정 고조", 0.3, "진심"), ("여운", 0.2, "감동/비극")],
    "foreshadow_payoff": [("복선 심기", 0.2, "평범한 소품/행동"), ("관계 전개", 0.3, "이야기 진행"), ("위기", 0.25, "갈등"), ("복선 회수", 0.25, "소품이 핵심이 됨")],
    "parallel": [("인물 A", 0.25, "A의 이야기"), ("인물 B", 0.25, "B의 이야기"), ("교차", 0.25, "두 이야기가 스침"), ("연결", 0.25, "하나로 이어짐")],
    "open_ending": [("설정", 0.25, "상황"), ("전개", 0.3, "선택의 순간으로"), ("고조", 0.25, "결정 직전"), ("열린 결말", 0.2, "해석을 맡김")],
    "reverse_causality": [("결과", 0.15, "결과를 먼저"), ("원인 추적 1", 0.3, "되감기"), ("원인 추적 2", 0.3, "더 이전"), ("진짜 원인", 0.25, "인과 완성")],
    "repetition_variation": [("반복 1", 0.25, "기본 패턴"), ("반복 2", 0.25, "변주"), ("반복 3", 0.25, "더 큰 변주"), ("마지막 변주", 0.25, "예상 밖 결말")],
}
DEFAULT_CUT_S = {15: 1.5, 30: 2.0, 60: 3.0, 90: 3.5}
SHOT_CYCLE = ["클로즈업", "미디엄샷", "리버스 클로즈업", "와이드샷", "인서트", "투샷"]
KOREAN_SYLLABLES_PER_SEC = 5.0  # 대사 밀도 상한 기준(초당 음절)


def _round_half(x: float) -> float:
    return round(x * 2) / 2


def split_durations(total: float, parts: int) -> list[float]:
    base = [_round_half(total / parts)] * parts
    base[-1] = round(total - sum(base[:-1]), 2)
    if base[-1] <= 0:
        base = [round(total / parts, 2)] * parts
    return base


def build_payload(selection: dict[str, Any], concept: dict[str, Any], intake: dict[str, Any], labels: dict[str, Any],
                  avg_cut_s: float | None) -> dict[str, Any]:
    narrative = selection.get("narrative") or "twist"
    seconds = concept["concept"]["duration_s"]
    action_mode = any('액션' in str(value) for value in (concept["concept"].get("genres", []), labels.get("genre", "")))
    return {
        "profile": "action" if action_mode else "default",
        "request": intake.get("request", ""),
        "selection": {k: v for k, v in selection.items() if k != "sources"},
        "selection_labels": labels,
        "concept": concept["concept"],
        "direction_rules": concept.get("direction_rules", {}),
        "constraints": intake.get("constraints", []) + selection.get("constraints", []),
        "free_text": selection.get("free_text", {}),
        "duration_s": seconds,
        "avg_cut_s": avg_cut_s or DEFAULT_CUT_S.get(seconds, 3.0),
        "structure_guide": [{"label": b[0], "ratio": b[1], "purpose": b[2]} for b in NARRATIVE_TEMPLATES.get(narrative, NARRATIVE_TEMPLATES["twist"])],
        "output_format_example": "examples/plans/interviewer-ex-girlfriend.plan.json",
        "rules": [
            "모든 컷 길이의 합 = duration_s",
            "씬은 시간 순서대로 이어지고 겹치지 않는다",
            "대사는 초당 5음절을 넘지 않는다",
            "무음성(no_speech) 제약이면 dialogue는 비우고 sound에 효과음·음악만 쓴다",
            "실존 작품의 장면·대사·캐릭터를 복제하지 않는다",
        ],
    }


def mock_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """결정론적 템플릿 기획안(오프라인). 구조·타이밍·필드가 완전하도록 채운다."""
    from .action import action_cuts

    seconds = float(payload["duration_s"])
    concept = payload["concept"]
    labels = payload.get("selection_labels", {})
    no_speech = "no_speech" in payload.get("constraints", [])
    free = payload.get("free_text", {})
    lead_name = (free.get("lead_character") or "주인공 A").split(",")[0].strip()[:20]
    characters = [
        {"id": "CH01", "name": lead_name, "age": 27, "role": "주연", "persona": "목표가 분명하지만 결정적 순간에 망설인다",
         "appearance": "어깨 길이 흑발, 갸름한 얼굴, 맑은 눈", "wardrobe": "아이보리 니트, 청바지, 흰 운동화", "voice": "무음성" if no_speech else "또렷한 중음"},
        {"id": "CH02", "name": "상대역 B", "age": 29, "role": "조연", "persona": "침착한 표정으로 상대를 당황시킨다",
         "appearance": "짧은 흑발, 단정한 인상", "wardrobe": "네이비 셔츠, 슬랙스", "voice": "무음성" if no_speech else "낮은 저음"},
    ]
    setting = (labels.get("setting") or ["실내 공간"])[0] if isinstance(labels.get("setting"), list) else labels.get("setting") or "실내 공간"
    avg = float(payload.get("avg_cut_s", 3.0))
    beats = payload["structure_guide"]
    scene_lengths = split_durations(seconds, len(beats))
    # 비율 반영
    raw = [b["ratio"] * seconds for b in beats]
    scene_lengths = [_round_half(x) for x in raw]
    scene_lengths[-1] = round(seconds - sum(scene_lengths[:-1]), 2)
    scenes, timeline, t, cut_no = [], [], 0.0, 0
    for s_idx, (beat, length) in enumerate(zip(beats, scene_lengths), start=1):
        n_cuts = max(1, int(math.floor(length / avg + 0.5)))
        cut_lengths = split_durations(length, n_cuts)
        cuts = []
        if payload.get("profile") == "action":
            cuts = action_cuts(length, characters, beat["purpose"])
            for offset, row in enumerate(cuts):
                row["no"] = cut_no + offset + 1
            cut_no += len(cuts)
        for c_idx, cl in enumerate([] if payload.get("profile") == "action" else cut_lengths):
            cut_no += 1
            who = characters[(cut_no + 1) % 2]
            shot = SHOT_CYCLE[(cut_no - 1) % len(SHOT_CYCLE)]
            line = "" if no_speech or shot in ("인서트", "와이드샷") else f"({beat['label']}) 짧은 대사"
            cuts.append({
                "no": cut_no, "duration": cl, "shot": shot,
                "visual": f"{who['name']} {shot}, {beat['purpose']}",
                "sound": ("대사 + 앰비언스" if line else
                           f"효과음: {beat['purpose']} 동작음" if shot in ("인서트", "와이드샷") else "앰비언스"),
                "dialogue": line, "speaker": who["id"] if line else None,
                "characters": [c["id"] for c in characters] if shot == "투샷" else [who["id"]],
            })
        scenes.append({"no": s_idx, "title": beat["label"], "start": round(t, 2), "end": round(t + length, 2),
                       "location": setting, "summary": beat["purpose"], "cuts": cuts,
                       "direction_note": "; ".join(payload.get("direction_rules", {}).get("camera_edit", [])[:2]) or "감정 변화에 맞춘 컷 리듬"})
        timeline.append({"start": round(t, 2), "end": round(t + length, 2), "label": beat["label"], "scene_no": s_idx,
                         "summary": beat["purpose"]})
        t += length
    first_line = "" if no_speech else "결정적인 한 마디"
    title = f"《{concept['title_line']}》"
    return {
        "version": "1.0", "generated_by": "mock", "title": title,
        "logline": f"{lead_name}에게 예상치 못한 사건이 일어나고, 마지막에 그 의미가 드러난다.",
        "meta": {"profile": payload.get("profile", "default"), "format": concept["format"], "genres": concept.get("genres", []) + concept.get("subgenres", []),
                 "runtime_s": seconds, "scene_count": len(scenes), "cut_count": cut_no, "aspect": concept["aspect"],
                 "style": concept["subtitle"], "narrative": concept.get("narrative") or "", "strategy": " → ".join(b["label"] for b in beats)},
        "synopsis": f"[목업 초안] {concept['title_line']}. {concept.get('chain', '')}. 감정 곡선: {concept.get('emotion_arc', '')}.",
        "hook": {"start": 0, "end": scenes[0]["end"], "line": first_line, "visual": scenes[0]["cuts"][0]["visual"],
                 "caption": f"{concept['title_line']} — 끝까지 보면 의미가 바뀐다", "questions": ["무슨 일이 일어난 걸까?", "왜 저런 선택을 했을까?", "결말은 어떻게 될까?"]},
        "timeline": timeline, "scenes": scenes, "characters": characters,
        "props": payload.get("direction_rules", {}).get("props_wardrobe", [])[:3] or ["핵심 소품 1개"],
        "production_spec": {"aspect": concept["aspect"], "fps": "24fps", "camera": "대화 35·50mm, 반응 85mm 느낌",
                            "lighting": "자연광 기반 + 인물 보조광", "edit": "; ".join(payload.get("direction_rules", {}).get("camera_edit", [])) or "감정 리듬 중심 컷",
                            "camera_movement": "긴장 시 슬로 푸시인", "bgm": "감정 곡선에 맞춘 테마", "sfx": "; ".join(payload.get("direction_rules", {}).get("music_sfx", [])) or "상황 효과음",
                            "grading": "자연스러운 피부색, 중간 대비", "subtitles": "KR+EN 하단 자막, 강조 단어 색상"},
        "preflight_checks": [],
    }


SYLLABLE = re.compile(r"[가-힣]")


def preflight(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """기획안 사전 점검(제작 전 확인 사항) — 타이밍 합계·연속성·대사 밀도·등장인물/공간 수."""
    checks: list[dict[str, Any]] = []
    runtime = float(plan["meta"]["runtime_s"])
    total = sum(float(c["duration"]) for s in plan["scenes"] for c in s["cuts"])
    checks.append({"id": "P01", "item": "컷 길이 합계 = 러닝타임", "status": "pass" if abs(total - runtime) <= 0.5 else "fail",
                   "detail": f"합계 {total:.1f}s / 러닝타임 {runtime:.1f}s"})
    prev_end, gaps = 0.0, []
    for s in plan["scenes"]:
        if abs(float(s["start"]) - prev_end) > 0.01:
            gaps.append(f"씬{s['no']} 시작 {s['start']} ≠ 이전 끝 {prev_end}")
        scene_sum = sum(float(c["duration"]) for c in s["cuts"])
        if abs(scene_sum - (float(s["end"]) - float(s["start"]))) > 0.5:
            gaps.append(f"씬{s['no']} 컷 합계 {scene_sum:.1f}s ≠ 씬 길이 {float(s['end']) - float(s['start']):.1f}s")
        prev_end = float(s["end"])
    checks.append({"id": "P02", "item": "씬 타임라인 연속성", "status": "pass" if not gaps else "fail", "detail": "; ".join(gaps) or "연속"})
    dense = []
    for s in plan["scenes"]:
        for c in s["cuts"]:
            syl = len(SYLLABLE.findall(c.get("dialogue") or ""))
            if syl and syl / max(float(c["duration"]), 0.1) > KOREAN_SYLLABLES_PER_SEC:
                dense.append(f"컷{c['no']}({syl}음절/{c['duration']}s)")
    checks.append({"id": "P03", "item": "대사 밀도(초당 5음절 이하)", "status": "pass" if not dense else "warn",
                   "detail": ", ".join(dense) or "적정", "fix": "대사를 줄이거나 컷을 늘리세요(2~4컷 조정)." if dense else None})
    n_chars, n_locs = len(plan["characters"]), len({s.get("location") for s in plan["scenes"]})
    checks.append({"id": "P04", "item": "등장인물·공간 수(AI 일관성)", "status": "pass" if n_chars <= 4 and n_locs <= 3 else "warn",
                   "detail": f"인물 {n_chars}명, 공간 {n_locs}곳"})
    ids = {c["id"] for c in plan["characters"]}
    unknown = sorted({sp for s in plan["scenes"] for c in s["cuts"] if (sp := c.get("speaker")) and sp not in ids})
    checks.append({"id": "P05", "item": "화자가 캐릭터 목록에 있음", "status": "pass" if not unknown else "fail", "detail": ", ".join(unknown) or "OK"})
    short = [c["no"] for s in plan["scenes"] for c in s["cuts"] if float(c["duration"]) < 0.5]
    checks.append({"id": "P06", "item": "최소 컷 길이 0.5초", "status": "pass" if not short else "warn", "detail": f"{short}" if short else "OK"})
    twist_needed = any(k in (plan["meta"].get("narrative") or "") for k in ("반전", "결말 선공개", "회수"))
    if twist_needed:
        checks.append({"id": "P07", "item": "반전·회수의 개연성 단서", "status": "review",
                       "detail": "반전 이전 씬에 단서(복선)가 최소 1개 있는지 검수자가 확인"})
    return checks


def generate_plan(router: Any, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    schema = load_schema("plan")
    plan, provider = router.generate("plan_v1", payload, schema)
    errors = validate_with_schema(plan, schema)
    if errors:
        raise ValueError("기획안이 스키마를 만족하지 않습니다: " + "; ".join(errors[:8]))
    plan.setdefault("generated_by", provider)
    plan["preflight_checks"] = plan.get("preflight_checks") or []
    plan["preflight_checks"] = [c for c in plan["preflight_checks"] if isinstance(c, dict) and c.get("id", "").startswith("U")] + preflight(plan)
    return plan, provider


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
