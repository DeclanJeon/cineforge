"""8종 SSOT(Single Source of Truth) 생성·버전 관리·변경 영향 분석(L2)."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cineforge.schemas import validate

SSOT_TYPES = ["concept", "story", "character", "world", "scene", "camera", "motion", "audio"]
# SSOT → 직접 영향을 받는 SSOT/산출물 (변경 영향 관리)
DEPENDENTS: dict[str, list[str]] = {
    "concept": ["story", "character", "world", "scene", "camera", "motion", "audio", "plan"],
    "story": ["scene", "audio"],
    "character": ["scene", "assets/image_prompts", "assets/video_prompts", "assets/frames", "audio"],
    "world": ["scene", "assets/image_prompts", "assets/video_prompts"],
    "scene": ["camera", "motion", "assets/frames", "assets/image_prompts", "assets/video_prompts", "assets/sound_cue_sheet"],
    "camera": ["assets/frames", "assets/video_prompts"],
    "motion": ["assets/video_prompts"],
    "audio": ["assets/sound_cue_sheet"],
}
DEPENDS_ON: dict[str, list[str]] = {t: [s for s, deps in DEPENDENTS.items() if t in deps] for t in SSOT_TYPES}
LENS_BY_SHOT = {"익스트림 클로즈업": 100, "클로즈업": 85, "리버스 클로즈업": 85, "미디엄샷": 50, "미디엄": 50, "투샷": 35,
                "와이드샷": 24, "와이드": 24, "인서트": 100, "풀샷": 35}


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def digest(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def impact(changed: str) -> list[str]:
    """변경된 SSOT로부터 전이적으로 영향받는 대상(순서 유지)."""
    seen: list[str] = []
    queue = list(DEPENDENTS.get(changed, []))
    while queue:
        item = queue.pop(0)
        if item in seen:
            continue
        seen.append(item)
        queue.extend(DEPENDENTS.get(item, []))
    return seen


class SSOTStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.dir = self.root / "ssot"

    def path(self, kind: str) -> Path:
        return self.dir / f"{kind}.json"

    def read(self, kind: str) -> dict[str, Any] | None:
        p = self.path(kind)
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    def versions(self) -> dict[str, int]:
        out = {}
        for kind in SSOT_TYPES:
            doc = self.read(kind)
            if doc:
                out[kind] = doc["version"]
        return out

    def write(self, kind: str, data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """데이터가 바뀌었을 때만 버전을 올린다. 잠긴(locked) SSOT는 덮어쓰지 않는다."""
        if kind not in SSOT_TYPES:
            raise KeyError(kind)
        current = self.read(kind)
        h = digest(data)
        if current and current["source_hash"] == h:
            return current, False
        if current and current.get("locked"):
            raise PermissionError(f"{kind} SSOT가 잠겨 있습니다(locked). `cineforge unlock`으로 해제 후 수정하세요.")
        doc = {"ssot_type": kind, "version": (current["version"] + 1) if current else 1, "updated_at": now(),
               "source_hash": h, "locked": False, "depends_on": DEPENDS_ON[kind],
               "upstream_versions": {k: v for k, v in self.versions().items() if k in DEPENDS_ON[kind]}, "data": data}
        errors = validate(doc, f"ssot_{kind}")
        if errors:
            raise ValueError(f"{kind} SSOT 스키마 오류: {errors[:5]}")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path(kind).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        with (self.root / "history.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps({"at": doc["updated_at"], "event": "ssot_write", "ssot": kind, "version": doc["version"],
                                  "hash": h, "impacts": impact(kind) if current else []}, ensure_ascii=False) + "\n")
        return doc, True

    def set_lock(self, kind: str, locked: bool) -> None:
        doc = self.read(kind)
        if not doc:
            raise FileNotFoundError(kind)
        doc["locked"] = locked
        self.path(kind).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_state(base: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in (patch or {}).items():
        if key == "holding":
            for ch, hands in value.items():
                out["holding"].setdefault(ch, {"left": None, "right": None}).update(hands)
        elif isinstance(value, dict):
            out.setdefault(key, {}).update(value)
        else:
            out[key] = value
    return out


def build_all(plan: dict[str, Any], concept: dict[str, Any], selection: dict[str, Any], tax_labels: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """기획안에서 8종 SSOT 데이터를 도출한다(이후 단계 스킬이 보강·잠금)."""
    rules = concept.get("direction_rules", {})
    chars = plan["characters"]
    char_ids = [c["id"] for c in chars]
    # A voice-over speaker (on_screen: false) is heard, never placed in frame.
    visible = [c["id"] for c in chars if c.get("on_screen", True) is not False]
    locations: dict[str, dict[str, Any]] = {}
    for s in plan["scenes"]:
        name = s.get("location") or "미정 공간"
        if name not in locations:
            locations[name] = {"id": f"LOC{len(locations) + 1:02d}", "name": name, "description": name,
                               "layout": "출입구는 화면 왼쪽, 창은 오른쪽(고정 레이아웃)", "lighting": plan["production_spec"].get("lighting", "")}
    concept_data = {
        "title": plan["title"], "title_line": concept["concept"]["title_line"], "subtitle": concept["concept"]["subtitle"],
        "chain": concept["concept"].get("chain", ""), "emotion_arc": concept["concept"].get("emotion_arc", ""),
        "selection": {k: v for k, v in selection.items() if k not in ("sources", "free_text")},
        "tone": plan["production_spec"].get("grading", ""), "forbidden_props": rules.get("forbidden_props", []),
        "direction_rules": rules, "overrides": selection.get("overrides", []),
    }
    screen = [s["no"] for s in plan["scenes"]]
    story_order = screen[1:] + screen[:1] if "결말 선공개" in (plan["meta"].get("narrative") or "") or "인과 역전" in (plan["meta"].get("narrative") or "") else list(screen)
    story = {
        "logline": plan["logline"], "synopsis": plan["synopsis"], "screen_order": screen, "story_order": story_order,
        "beats": [{"scene_no": t["scene_no"], "label": t["label"], "summary": t.get("summary", "")} for t in plan["timeline"]],
        "foreshadowing": [{"id": f"FS{i + 1:02d}", "item": p, "plant_cut": None, "payoff_cut": None} for i, p in enumerate(plan.get("foreshadowing", []))],
        "twists": [t["label"] for t in plan["timeline"] if "반전" in t["label"]],
        "causality": [{"from": a, "to": b, "because": f"씬{a}의 결과가 씬{b}을(를) 촉발"} for a, b in zip(story_order, story_order[1:])],
    }
    character = {"characters": [{
        "id": c["id"], "name": c["name"], "age": c.get("age"), "role": c["role"], "persona": c["persona"], "appearance": c["appearance"],
        "identity_anchor": f"{c['name']}: {c['appearance']}",
        "wardrobe": [{"id": f"{c['id']}-W1", "description": c["wardrobe"], "scenes": screen}],
        "voice": {"type": "silent" if "무음" in (c.get("voice") or "") or "no_speech" in selection.get("constraints", []) else "dialogue",
                  "description": c.get("voice") or ""},
        "consent": {"real_person": bool(c.get("real_person", False)), "likeness_consent": c.get("likeness_consent")},
        "on_screen": c.get("on_screen", True) is not False,
    } for c in chars]}
    world = {"era": tax_labels.get("era"), "world": tax_labels.get("world"),
             "rules": [r for r in [tax_labels.get("world") and f"세계관 규칙: {tax_labels['world']}", tax_labels.get("era") and f"시대 고증: {tax_labels['era']}"] if r],
             "locations": list(locations.values()),
             "props": [{"id": f"PR{i + 1:02d}", "name": p, "era_valid": True} for i, p in enumerate(plan.get("props", []))],
             "forbidden_props": rules.get("forbidden_props", [])}
    cuts, cams, motions = [], [], []
    positions_default = {cid: ("left" if i == 0 else "right" if i == 1 else "center") for i, cid in enumerate(visible)}
    for s in plan["scenes"]:
        loc = locations[s.get("location") or "미정 공간"]["id"]
        carry = {"positions": dict(positions_default), "holding": {cid: {"left": None, "right": None} for cid in char_ids},
                 "wardrobe": {cid: f"{cid}-W1" for cid in char_ids}, "gaze": {}, "lighting": loc and locations[s.get("location") or "미정 공간"]["lighting"]}
        t = float(s["start"])
        for c in s["cuts"]:
            st = c.get("state") or {}
            start_state = _merge_state(carry, st.get("start"))
            end_state = _merge_state(start_state, st.get("end"))
            cut_id = f"S{s['no']:02d}C{c['no']:02d}"
            if "characters" in c:  # an explicit empty list means nobody is in frame
                present = [cid for cid in c["characters"] if cid in visible]
            elif c.get("speaker"):
                present = [c["speaker"]] if c["speaker"] in visible else []
            else:
                present = visible[:1]
            cuts.append({"cut_id": cut_id, "scene_no": s["no"], "cut_no": c["no"], "start": round(t, 2), "end": round(t + float(c["duration"]), 2),
                         "duration": float(c["duration"]), "location_id": loc, "characters": present, "start_state": start_state, "end_state": end_state,
                         "state_changes": st.get("changes", []), "dialogue": c.get("dialogue") or None, "speaker": c.get("speaker"), "visual": c["visual"],
                         "sound": c.get("sound") or "", "impact": bool(c.get("impact", False)),
                         "beat": c.get("beat")})
            shot = c.get("shot") or "미디엄샷"
            cams.append({"cut_id": cut_id, "shot_size": shot, "lens_mm": int(c.get("lens_mm") or LENS_BY_SHOT.get(shot, 50)),
                         "angle": c.get("angle", "아이레벨"), "movement": c.get("camera", "고정"), "axis_side": c.get("axis_side", "A"),
                         "screen_direction": c.get("screen_direction"), "crosses_axis": bool(st.get("crosses_axis", False))})
            motions.append({"cut_id": cut_id, "action": c["visual"], "direction": c.get("screen_direction"), "speed": c.get("speed", "보통"),
                            "contact": st.get("contact", [])})
            carry = end_state
            t += float(c["duration"])
    silent = selection.get("direction", {}).get("sound") == "silent" or "no_speech" in selection.get("constraints", [])
    voice_led = selection.get("direction", {}).get("sound") == "narration_driven"
    from .audio_design import cues_from_plan
    cues = cues_from_plan(cuts, plan, silent, voice_led=voice_led)
    audio = {"voices": [{"character_id": c["id"], "type": "silent" if silent else "dialogue", "description": c.get("voice", "")} for c in chars],
             "music_themes": [
                 {"id": "TH01", "description": f"주제가(OST): {plan.get('title', '')} — {plan['production_spec'].get('bgm', '')}",
                  "license": "original-to-generate", "vocal": not silent and not voice_led},
                 {"id": "TH02", "description": f"언더스코어: {plan['production_spec'].get('bgm', '')}", "license": "original-to-generate", "vocal": False}],
             "ambience": [{"location_id": l["id"], "description": f"{l['name']} 공간음"} for l in locations.values()],
             "cues": cues}
    return {"concept": concept_data, "story": story, "character": character, "world": world, "scene": {"cuts": cuts},
            "camera": {"cuts": cams}, "motion": {"cuts": motions}, "audio": audio}


def build_cues(cuts: list[dict[str, Any]], plan: dict[str, Any], silent: bool) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    n = 0

    def add(kind: str, tc_in: float, tc_out: float, cut_id: str | None, desc: str, source: str, license_: str, level: str = "-12 LUFS 기준") -> None:
        nonlocal n
        n += 1
        cues.append({"cue_id": f"Q{n:03d}", "type": kind, "tc_in": round(tc_in, 2), "tc_out": round(tc_out, 2), "cut_id": cut_id,
                     "description": desc, "level": level, "source": source, "license": license_, "notes": ""})

    for s in plan["scenes"]:
        add("BGM", float(s["start"]), float(s["end"]), None, f"씬{s['no']} {s['title']} — {plan['production_spec'].get('bgm', '')}",
            "generate", "original-to-generate", "-20 dB under")
    for c in cuts:
        if c.get("dialogue") and not silent:
            add("DIALOGUE", c["start"], c["end"], c["cut_id"], f"{c.get('speaker')}: {c['dialogue']}", "generate-in-video", "original")
    for s in plan["scenes"]:
        for c in s["cuts"]:
            sound = c.get("sound") or ""
            if any(k in sound for k in ("효과음", "소리", "스크래치", "타격", "낙하음", "SFX", "임팩트")):
                cut = next(x for x in cuts if x["scene_no"] == s["no"] and x["cut_no"] == c["no"])
                add("SFX", cut["start"], cut["end"], cut["cut_id"], sound, "generate", "original-to-generate")
    cues.sort(key=lambda q: (q["tc_in"], q["type"]))
    return cues
