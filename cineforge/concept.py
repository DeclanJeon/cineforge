"""S02 콘셉트 조합 엔진(E03) + 적합성 검사(L1) + 아이디어 평가 엔진(E04) + 콘셉트→연출 규칙 변환."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from cineforge.data_loader import load
from cineforge.providers.base import Question
from cineforge.providers.router import ProviderRouter
from cineforge.taxonomy import Taxonomy

SCORE_LEVELS = ["매우 낮음", "낮음", "보통", "높음", "매우 높음"]
LEVEL_VALUE = {lvl: 10 + 20 * i for i, lvl in enumerate(SCORE_LEVELS)}  # 10,30,50,70,90
WEIGHTS = {"hook": 0.25, "feasibility": 0.20, "emotion": 0.15, "originality": 0.15, "coherence": 0.15, "platform_fit": 0.10}
DIMENSIONS = {
    "hook": "첫 3초 후킹 강도: 시청자가 이탈하지 않고 다음 장면을 궁금해할 가능성",
    "feasibility": "AI 영상 생성으로 일관되게 제작 가능한 정도(인물 수·공간 수·카메라 난이도·길이)",
    "emotion": "감정 목표가 분명하고 곡선(대비)이 살아 있는 정도",
    "originality": "흔한 조합이 아닌 신선함과 구체성",
    "coherence": "선택한 속성들이 서로 충돌하지 않고 하나의 작품으로 묶이는 정도",
    "platform_fit": "숏폼 플랫폼(9:16·60초 이하) 적합성",
}


def _value_of(sel: dict[str, Any], key: str) -> list[str]:
    if key.startswith("direction."):
        v = sel.get("direction", {}).get(key.split(".", 1)[1])
    else:
        v = sel.get(key)
    if v is None:
        return []
    return list(v) if isinstance(v, list) else [v]


def _matches(sel: dict[str, Any], when: dict[str, Any]) -> bool:
    for key, expected in when.items():
        have = _value_of(sel, key)
        wanted = expected if isinstance(expected, list) else [expected]
        if not set(have) & set(wanted):
            return False
    return True


def compatibility(sel: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    overrides = set(sel.get("overrides", []))
    for rule in load("rules.yaml")["compatibility"]:
        if _matches(sel, rule["when"]):
            overridden = rule["id"] in overrides and rule.get("override", False)
            issues.append({"rule": rule["id"], "severity": rule["severity"], "message": rule["msg"],
                           "fix": rule.get("fix"), "overridable": rule.get("override", False),
                           "overridden": overridden})
    if "no_speech" in sel.get("constraints", []) and sel.get("direction", {}).get("sound") in ("dialogue_driven", "narration_driven"):
        issues.append({"rule": "C100", "severity": "error", "message": "무음성 제약인데 사운드가 대사/내레이션 중심입니다.",
                       "fix": "사운드를 무성·음악 중심·ASMR 중 하나로 바꾸세요.", "overridable": False, "overridden": False})
    return issues


def blocking(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [i for i in issues if i["severity"] == "error" and not i["overridden"]]


def direction_rules(sel: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {"applied": []}
    for pack in load("rules.yaml")["direction_rules"]:
        if not _matches(sel, pack["when"]):
            continue
        merged["applied"].append(pack["id"])
        for key, value in pack["rules"].items():
            if isinstance(value, list):
                merged.setdefault(key, [])
                merged[key] += [v for v in value if v not in merged[key]]
            else:
                merged.setdefault(key, value)
    return merged


def duration_seconds(sel: dict[str, Any], tax: Taxonomy) -> int:
    if sel.get("duration"):
        return int(tax.get("duration", sel["duration"]).data["seconds"])
    return int(sel.get("duration_custom_s") or 60)


def combine(sel: dict[str, Any], tax: Taxonomy) -> dict[str, Any]:
    """선택값을 하나의 제작 콘셉트 문장/태그로 조합한다."""
    seconds = duration_seconds(sel, tax)
    fmt = tax.get("format", sel["format"]).ko if sel.get("format") else "영상"
    genres = tax.labels("genre", sel.get("genre") or [])
    sub = tax.labels("subgenre", sel.get("subgenre") or [])
    headline_genre = genres[0] if genres else (sub[0] if sub else "")
    title_line = f"{seconds}초 {headline_genre + ' ' if headline_genre else ''}{fmt}".strip()
    style_bits: list[str] = []
    d = sel.get("direction", {})
    if d.get("texture"):
        style_bits.append(tax.get("direction", d["texture"], "texture").ko)
    if d.get("expression"):
        style_bits.append(tax.get("direction", d["expression"], "expression").ko)
    elif sel.get("production_method"):
        style_bits.append(tax.get("production_method", sel["production_method"]).ko)
    narrative = tax.get("narrative", sel["narrative"]).ko if sel.get("narrative") else None
    subtitle = " · ".join(filter(None, [(" ".join(style_bits) + " 연출") if style_bits else None,
                                         (narrative.rstrip("형") + " 서사") if narrative else None]))
    chain_axes = ["culture_style", "era", "genre", "romance_concept", "world", "story_nature", "subgenre",
                  "visual_aesthetic", "narrative"]
    chain: list[str] = []
    for axis_id in chain_axes:
        value = sel.get(axis_id)
        if value in (None, []):
            continue
        for label in tax.labels(axis_id, value if isinstance(value, list) else [value]):
            if label not in chain:
                chain.append(label)
    emotion = " → ".join(tax.labels("emotion_arc", sel.get("emotion_arc") or []))
    return {"title_line": title_line, "subtitle": subtitle, "chain": " × ".join(chain), "emotion_arc": emotion,
            "duration_s": seconds, "format": fmt, "genres": genres, "subgenres": sub, "narrative": narrative,
            "aspect": tax.get("aspect", sel["aspect"]).ko if sel.get("aspect") else "9:16 세로"}


def heuristic_scores(sel: dict[str, Any], tax: Taxonomy, issues: list[dict[str, Any]]) -> dict[str, float]:
    seconds = duration_seconds(sel, tax)
    narrative = tax.get("narrative", sel["narrative"]).data if sel.get("narrative") else {"hook_weight": 0.5, "complexity": 2}
    hook = narrative.get("hook_weight", 0.5) + (0.1 if sel.get("hook") else 0) + (0.05 if seconds <= 60 else -0.05)
    arc = sel.get("emotion_arc") or []
    emotion = {0: 0.3, 1: 0.6, 2: 0.85, 3: 0.75}.get(len(arc), 0.6)
    method = tax.get("production_method", sel["production_method"]).data if sel.get("production_method") else {}
    camera = sel.get("direction", {}).get("camera")
    cam_diff = tax.get("direction", camera, "camera").data.get("ai_difficulty", 1) if camera else 1
    errors = len(blocking(issues))
    warns = len([i for i in issues if i["severity"] == "warn" and not i["overridden"]])
    feasibility = 1.0 - 0.1 * method.get("ai_difficulty", 1) - 0.08 * cam_diff - 0.07 * narrative.get("complexity", 2) \
        - (0.1 if seconds > 60 else 0) - 0.25 * errors
    optional = ["culture_style", "era", "subgenre", "romance_concept", "world", "story_nature", "setting",
                "relationship", "visual_aesthetic", "hook"]
    specificity = sum(1 for a in optional if sel.get(a) not in (None, []))
    originality = 0.35 + 0.06 * specificity + (0.1 if sel.get("culture_style") and sel.get("world") else 0)
    coherence = 1.0 - 0.35 * errors - 0.08 * warns
    aspect = sel.get("aspect")
    platform = (0.9 if aspect == "r9_16" else 0.6) - (0.15 if seconds > 60 else 0)
    clamp = lambda x: round(max(0.0, min(1.0, x)), 3)  # noqa: E731
    return {"hook": clamp(hook), "emotion": clamp(emotion), "feasibility": clamp(feasibility),
            "originality": clamp(originality), "coherence": clamp(coherence), "platform_fit": clamp(platform)}


def evaluate(sel: dict[str, Any], tax: Taxonomy, router: ProviderRouter, issues: list[dict[str, Any]],
             combo: dict[str, Any], task: str = "evaluate") -> dict[str, Any]:
    heur = heuristic_scores(sel, tax, issues)
    questions = [Question(f"score_{dim}", "score", f"이 영상 콘셉트의 {desc}는?", SCORE_LEVELS,
                          hints={"score": heur[dim]}) for dim, desc in DIMENSIONS.items()]
    state = {"concept": combo, "selection": {k: v for k, v in sel.items() if k not in ("sources",)},
             "compatibility": issues}
    answers = router.decide(state, questions, task=task)
    scores = {dim: LEVEL_VALUE.get(str(answers[f"score_{dim}"].value), 50) for dim in DIMENSIONS}
    total = round(sum(scores[d] * w for d, w in WEIGHTS.items()), 1)
    verdict = "go" if total >= 65 and not blocking(issues) else ("revise" if total >= 50 else "rework")
    provider = sorted({a.provider for a in answers.values()})
    return {"scores": scores, "total": total, "verdict": verdict, "weights": WEIGHTS, "providers": provider}


def candidates(sel: dict[str, Any], tax: Taxonomy, router: ProviderRouter, limit: int = 2) -> list[dict[str, Any]]:
    """대안 후보: 서사 구조를 후킹 가중치가 높은 다른 구조로 바꾼 변형을 만들어 함께 평가한다."""
    current = sel.get("narrative")
    pool = sorted(tax.items("narrative"), key=lambda i: -i.data.get("hook_weight", 0))
    out: list[dict[str, Any]] = []
    for item in pool:
        if item.id == current:
            continue
        variant = deepcopy(sel)
        variant["narrative"] = item.id
        issues = compatibility(variant)
        if blocking(issues):
            continue
        combo = combine(variant, tax)
        ev = evaluate(variant, tax, router, issues, combo, task=f"evaluate_alt_{item.id}")
        out.append({"change": {"narrative": item.id}, "label": f"서사 → {item.ko}", "concept": combo, "evaluation": ev})
        if len(out) >= limit:
            break
    return out


def build_concept(sel: dict[str, Any], tax: Taxonomy, router: ProviderRouter, with_candidates: bool = True) -> dict[str, Any]:
    issues = compatibility(sel)
    combo = combine(sel, tax)
    ev = evaluate(sel, tax, router, issues, combo)
    result = {"concept": combo, "compatibility": issues, "blocking": blocking(issues), "evaluation": ev,
              "direction_rules": direction_rules(sel), "candidates": []}
    if with_candidates:
        result["candidates"] = candidates(sel, tax, router)
    return result
