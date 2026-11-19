"""검수 규칙 — 연속성(L3), 제약·적합성(L1), 권리·안전(L5), 비용·리소스(L4).

규칙 ID는 docs/12-continuity-qa-rules.md 와 1:1로 대응한다.
"""
from __future__ import annotations

import re
from typing import Any

from cineforge.ssot import now

SYLLABLE = re.compile(r"[가-힣]")


def _issue(rule: str, severity: str, message: str, target: str | None = None) -> dict[str, Any]:
    return {"rule": rule, "severity": severity, "target": target, "message": message}


def continuity(ssots: dict[str, dict[str, Any]], runtime: float) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    cuts = ssots["scene"]["data"]["cuts"]
    cams = {c["cut_id"]: c for c in ssots["camera"]["data"]["cuts"]}
    char_ids = {c["id"] for c in ssots["character"]["data"]["characters"]}
    # CQ01 타이밍 합계
    total = sum(c["duration"] for c in cuts)
    if abs(total - runtime) > 0.5:
        issues.append(_issue("CQ01", "error", f"컷 합계 {total:.1f}s ≠ 러닝타임 {runtime:.1f}s"))
    prev = None
    for cut in cuts:
        cid = cut["cut_id"]
        # CQ05 화자/등장 인물 존재
        for who in cut["characters"]:
            if who not in char_ids:
                issues.append(_issue("CQ05", "error", f"알 수 없는 인물 {who}", cid))
        if cut.get("speaker") and cut["speaker"] not in cut["characters"]:
            issues.append(_issue("CQ05", "warn", f"화자 {cut['speaker']}가 컷 등장 인물에 없습니다(오프스크린이면 표시 필요)", cid))
        # CQ07 대사 밀도
        syl = len(SYLLABLE.findall(cut.get("dialogue") or ""))
        if syl and syl / max(cut["duration"], 0.1) > 5.0:
            issues.append(_issue("CQ07", "warn", f"대사 밀도 {syl / cut['duration']:.1f}음절/초 > 5", cid))
        if prev and prev["scene_no"] == cut["scene_no"]:
            justified = bool(cut.get("state_changes"))
            # CQ02 소품·손 상태 연속
            for who, hands in prev["end_state"]["holding"].items():
                now_hands = cut["start_state"]["holding"].get(who, {})
                for hand in ("left", "right"):
                    if hands.get(hand) != now_hands.get(hand) and not justified:
                        issues.append(_issue("CQ02", "error", f"{who} {hand} 손: 이전 컷 끝 '{hands.get(hand)}' → 이번 컷 시작 '{now_hands.get(hand)}'", cid))
            # CQ03 위치 연속
            for who, pos in prev["end_state"]["positions"].items():
                if who in cut["characters"] and cut["start_state"]["positions"].get(who) != pos and not justified:
                    issues.append(_issue("CQ03", "error", f"{who} 화면 위치 {pos} → {cut['start_state']['positions'].get(who)}", cid))
            # CQ04 의상 연속
            for who, w in prev["end_state"]["wardrobe"].items():
                if cut["start_state"]["wardrobe"].get(who) != w:
                    issues.append(_issue("CQ04", "error", f"{who} 의상 {w} → {cut['start_state']['wardrobe'].get(who)}", cid))
            # CQ06 조명 연속
            if prev["end_state"].get("lighting") != cut["start_state"].get("lighting") and not justified:
                issues.append(_issue("CQ06", "warn", "같은 씬 안에서 조명 상태가 바뀝니다", cid))
            # CQ08 180도 축
            a, b = cams[prev["cut_id"]], cams[cid]
            if a["axis_side"] != b["axis_side"] and not b.get("crosses_axis"):
                issues.append(_issue("CQ08", "error", f"시선축 {a['axis_side']}→{b['axis_side']} 이동(동기 없는 축 넘기)", cid))
        prev = cut
    return issues


def constraints(ssots: dict[str, dict[str, Any]], prompts: list[dict[str, Any]] | None = None,
                silent: bool = False, no_speech: bool = False) -> list[dict[str, Any]]:
    """CQ10 금지 소품(시대착오) — 컷 묘사·프롬프트에 금지 소품이 나오면 오류(override 시 info).
    CQ11 무음 연출/대사 없음 제약인데 기획안에 대사가 있으면 표시(대사 없음 제약은 오류, 무음 연출 선택은 경고)."""
    issues: list[dict[str, Any]] = []
    if silent or no_speech:
        spoken = [c["cut_id"] for c in ssots["scene"]["data"]["cuts"] if c.get("dialogue")]
        if spoken:
            issues.append(_issue("CQ11", "error" if no_speech else "warn",
                                 f"{'대사 없음 제약' if no_speech else '무음 연출 선택'}인데 대사가 있는 컷 {len(spoken)}개({', '.join(spoken[:5])}…) — 대사를 행동·자막으로 바꾸거나 사운드 연출을 변경"))
    forbidden = ssots["concept"]["data"].get("forbidden_props", [])
    overrides = set(ssots["concept"]["data"].get("overrides", []))
    texts = [(c["cut_id"], c["visual"] + " " + (c.get("dialogue") or "")) for c in ssots["scene"]["data"]["cuts"]]
    texts += [(p["prompt_id"], p["prompt"]) for p in (prompts or [])]
    for target, text in texts:
        for item in forbidden:
            if item and item in text:
                sev = "info" if "CQ10" in overrides else "error"
                issues.append(_issue("CQ10", sev, f"금지 소품/시대착오 '{item}' 등장", target))
    return issues


def identity(ssots: dict[str, dict[str, Any]], image_prompts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """CQ09 동일 인물은 모든 프롬프트에서 같은 identity_anchor 문자열을 써야 한다."""
    issues = []
    anchors = {c["id"]: c["identity_anchor"] for c in ssots["character"]["data"]["characters"]}
    cuts = {c["cut_id"]: c for c in ssots["scene"]["data"]["cuts"]}
    for p in image_prompts:
        if p["kind"] not in ("start_frame", "end_frame"):
            continue
        for cid in cuts[p["cut_id"]]["characters"]:
            if cid in anchors and anchors[cid] not in p["prompt"]:
                issues.append(_issue("CQ09", "error", f"{cid} 정체성 앵커 누락", p["prompt_id"]))
    return issues


def rights_safety(ssots: dict[str, dict[str, Any]], selection: dict[str, Any], intake: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    for c in ssots["character"]["data"]["characters"]:
        if c["consent"]["real_person"] and not c["consent"]["likeness_consent"]:
            issues.append(_issue("RS01", "error", f"실존 인물 {c['name']}의 초상·음성 사용 동의가 기록되지 않았습니다", c["id"]))
    for q in ssots["audio"]["data"]["cues"]:
        if q["license"] in ("", "UNVERIFIED", "unknown"):
            issues.append(_issue("RS02", "error", "음원 라이선스 미확인", q["cue_id"]))
    if intake.get("factors", {}).get("reference", {}).get("status") == "provided" or selection.get("free_text", {}).get("reference"):
        issues.append(_issue("RS03", "info", "레퍼런스는 구조·리듬만 참고하고 원본 영상·음악·대사·캐릭터를 재사용하지 않습니다(출처 기록 필요)"))
    if "ai_persona_disclosure" in selection.get("constraints", []):
        issues.append(_issue("RS05", "info", "AI 페르소나 콘텐츠: 캡션·프로필에서 AI임을 숨기지 않음"))
    issues.append(_issue("RS04", "info", "AI 생성 콘텐츠 표기: 게시 시 플랫폼 AI 표시 기능·해시태그로 공개(영상 내 코너 라벨은 넣지 않음)"))
    return issues


def cost_plan(ssots: dict[str, dict[str, Any]], method_difficulty: int = 1) -> dict[str, Any]:
    """L4: 컷 난이도로 모델 등급을 배정(어려운 컷만 고비용). 단가는 실행 시점에 실제 확인(여기선 미확정)."""
    cams = {c["cut_id"]: c for c in ssots["camera"]["data"]["cuts"]}
    rows = []
    for cut in ssots["scene"]["data"]["cuts"]:
        cam = cams[cut["cut_id"]]
        score = method_difficulty + len(cut["characters"]) + (2 if cam["movement"] not in ("고정", "") else 0) \
            + (1 if cut.get("state_changes") else 0) + (1 if cut["duration"] > 5 else 0)
        rows.append({"cut_id": cut["cut_id"], "difficulty": score})
    rows.sort(key=lambda r: -r["difficulty"])
    top = max(1, len(rows) // 5)
    for i, r in enumerate(rows):
        r["tier"] = "high" if i < top else "standard"
    return {"cuts": sorted(rows, key=lambda r: r["cut_id"]), "high_tier_cuts": top, "unit_price": "UNVERIFIED — 실행 직전 공급자 가격을 실제 조회",
            "regeneration_policy": "검수 실패 컷과 그 의존 대상만 재생성(변경 영향 분석 결과 기준)"}


def report(gate: str, issues: list[dict[str, Any]], summary: dict[str, Any] | None = None) -> dict[str, Any]:
    status = "fail" if any(i["severity"] == "error" for i in issues) else ("warn" if any(i["severity"] == "warn" for i in issues) else "pass")
    counts = {s: sum(1 for i in issues if i["severity"] == s) for s in ("error", "warn", "info")}
    return {"gate": gate, "status": status, "checked_at": now(), "issues": issues, "summary": dict(summary or {}, counts=counts)}
