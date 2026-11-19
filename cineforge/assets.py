"""S07 에셋 준비 — 에셋 레지스트리, 컷별 시작·종료 프레임, 이미지/영상 프롬프트, 사운드 큐 시트."""
from __future__ import annotations

from typing import Any

NEGATIVE_BASE = ["화면 속 글자·자막", "워터마크", "로고", "'Made with AI' 등 코너 라벨", "손가락 변형", "얼굴 변형", "인물 바뀜"]


def _ssot(ssots: dict[str, dict[str, Any]], kind: str) -> dict[str, Any]:
    return ssots[kind]["data"]


def _versions(ssots: dict[str, dict[str, Any]], kinds: list[str]) -> dict[str, int]:
    return {k: ssots[k]["version"] for k in kinds}


def registry(project_id: str, ssots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    for c in _ssot(ssots, "character")["characters"]:
        assets.append({"asset_id": f"A-{c['id']}-MASTER", "kind": "character_master", "name": c["name"], "version": 1,
                       "status": "planned", "path": None, "depends_on": ["ssot/character"]})
        for w in c["wardrobe"]:
            assets.append({"asset_id": f"A-{w['id']}", "kind": "wardrobe", "name": f"{c['name']} 의상: {w['description']}", "version": 1,
                           "status": "planned", "path": None, "depends_on": ["ssot/character"]})
    world = _ssot(ssots, "world")
    for loc in world["locations"]:
        assets.append({"asset_id": f"A-{loc['id']}", "kind": "location_plate", "name": loc["name"], "version": 1, "status": "planned",
                       "path": None, "depends_on": ["ssot/world"]})
    for p in world["props"]:
        assets.append({"asset_id": f"A-{p['id']}", "kind": "prop", "name": p["name"], "version": 1, "status": "planned", "path": None,
                       "depends_on": ["ssot/world"]})
    return {"project_id": project_id, "assets": assets}


def _describe_state(state: dict[str, Any], names: dict[str, str], present: list[str]) -> str:
    bits = []
    for cid in present:
        pos = state["positions"].get(cid, "center")
        hands = state["holding"].get(cid, {})
        held = ", ".join(f"{'왼손' if h == 'left' else '오른손'}에 {v}" for h, v in hands.items() if v)
        bits.append(f"{names.get(cid, cid)}(화면 {pos}{', ' + held if held else ''})")
    return "; ".join(bits)


def frames(project_id: str, ssots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    names = {c["id"]: c["name"] for c in _ssot(ssots, "character")["characters"]}
    cams = {c["cut_id"]: c for c in _ssot(ssots, "camera")["cuts"]}
    out = []
    for cut in _ssot(ssots, "scene")["cuts"]:
        cam = cams[cut["cut_id"]]
        out.append({"cut_id": cut["cut_id"],
                    "start_frame": {"composition": f"{cam['shot_size']} {cam['lens_mm']}mm {cam['angle']}", "subjects": _describe_state(cut["start_state"], names, cut["characters"]),
                                    "lighting": cut["start_state"].get("lighting", ""), "location_id": cut["location_id"]},
                    "end_frame": {"composition": f"{cam['shot_size']} ({cam['movement']} 후)", "subjects": _describe_state(cut["end_state"], names, cut["characters"]),
                                  "lighting": cut["end_state"].get("lighting", ""), "changes": cut.get("state_changes", [])}})
    return {"project_id": project_id, "frames": out}


def image_prompts(project_id: str, ssots: dict[str, dict[str, Any]], aspect: str, look: str) -> dict[str, Any]:
    concept = _ssot(ssots, "concept")
    chars = {c["id"]: c for c in _ssot(ssots, "character")["characters"]}
    locs = {l["id"]: l for l in _ssot(ssots, "world")["locations"]}
    cams = {c["cut_id"]: c for c in _ssot(ssots, "camera")["cuts"]}
    color = "; ".join(concept["direction_rules"].get("color_texture", [])) or look
    negative = ", ".join(NEGATIVE_BASE + concept.get("forbidden_props", []))
    prompts: list[dict[str, Any]] = []
    for c in chars.values():
        prompts.append({"prompt_id": f"IMG-{c['id']}-SHEET", "target": c["name"], "cut_id": None, "kind": "character_sheet",
                        "prompt": f"캐릭터 시트, 정면·측면·뒷모습 3면, 중립 표정과 감정 표정 4종. {c['identity_anchor']}. 의상: {c['wardrobe'][0]['description']}. {look}. 단색 배경.",
                        "negative": negative, "refs": [], "params": {"aspect": "16:9"}, "ssot_versions": _versions(ssots, ["character", "concept"])})
    for l in locs.values():
        prompts.append({"prompt_id": f"IMG-{l['id']}-PLATE", "target": l["name"], "cut_id": None, "kind": "location_plate",
                        "prompt": f"{l['name']} 배경 플레이트(인물 없음). 레이아웃: {l['layout']}. 조명: {l['lighting']}. {color}.",
                        "negative": negative, "refs": [], "params": {"aspect": aspect}, "ssot_versions": _versions(ssots, ["world", "concept"])})
    for cut in _ssot(ssots, "scene")["cuts"]:
        cam = cams[cut["cut_id"]]
        who = []
        for cid in cut["characters"]:
            ch = chars.get(cid)
            if not ch:
                continue
            pos = cut["start_state"]["positions"].get(cid, "center")
            held = [f"{'왼손' if h == 'left' else '오른손'}에 {v}" for h, v in cut["start_state"]["holding"].get(cid, {}).items() if v]
            who.append(f"{ch['identity_anchor']}, 의상 {ch['wardrobe'][0]['description']}, 화면 {pos}" + (", " + ", ".join(held) if held else ""))
        loc = locs.get(cut["location_id"], {"name": "", "lighting": ""})
        for kind, state_key in (("start_frame", "start_state"), ("end_frame", "end_state")):
            prompts.append({"prompt_id": f"IMG-{cut['cut_id']}-{'S' if kind == 'start_frame' else 'E'}", "target": cut["cut_id"], "cut_id": cut["cut_id"], "kind": kind,
                            "prompt": f"{look}. {cam['shot_size']}, {cam['lens_mm']}mm 렌즈 느낌, {cam['angle']}. 장소: {loc['name']}, {cut[state_key].get('lighting') or loc['lighting']}. "
                                      f"{' / '.join(who) or '인물 없음'}. 장면: {cut['visual']}. {color}.",
                            "negative": negative, "refs": [f"IMG-{cid}-SHEET" for cid in cut["characters"]] + [f"IMG-{cut['location_id']}-PLATE"],
                            "params": {"aspect": aspect}, "ssot_versions": _versions(ssots, ["character", "world", "scene", "camera"])})
    return {"project_id": project_id, "kind": "image", "prompts": prompts}


def video_prompts(project_id: str, ssots: dict[str, dict[str, Any]], aspect: str, silent: bool) -> dict[str, Any]:
    cams = {c["cut_id"]: c for c in _ssot(ssots, "camera")["cuts"]}
    motions = {m["cut_id"]: m for m in _ssot(ssots, "motion")["cuts"]}
    cues = _ssot(ssots, "audio")["cues"]
    prompts = []
    for cut in _ssot(ssots, "scene")["cuts"]:
        cam, mo = cams[cut["cut_id"]], motions[cut["cut_id"]]
        sfx = [q["description"] for q in cues if q.get("cut_id") == cut["cut_id"] and q["type"] == "SFX"]
        audio = "대사 없음. " if silent or not cut.get("dialogue") else f"대사({cut.get('speaker')}): \"{cut['dialogue']}\". "
        audio += ("효과음: " + "; ".join(sfx)) if sfx else "앰비언스 유지"
        prompts.append({"prompt_id": f"VID-{cut['cut_id']}", "target": cut["cut_id"], "cut_id": cut["cut_id"], "kind": "video",
                        "prompt": f"시작 프레임 IMG-{cut['cut_id']}-S 에서 종료 프레임 IMG-{cut['cut_id']}-E 로. 동작: {mo['action']} (속도 {mo['speed']}, 방향 {mo['direction']}). "
                                  f"카메라: {cam['movement']}, {cam['shot_size']}. 길이 {cut['duration']}초. 사운드: {audio}. 인물 얼굴·의상·소품 위치는 시작 프레임과 동일하게 유지.",
                        "negative": ", ".join(NEGATIVE_BASE), "refs": [f"IMG-{cut['cut_id']}-S", f"IMG-{cut['cut_id']}-E"],
                        "params": {"duration_s": cut["duration"], "aspect": aspect, "audio": not silent},
                        "ssot_versions": _versions(ssots, ["scene", "camera", "motion", "audio", "character"])})
    return {"project_id": project_id, "kind": "video", "prompts": prompts}


def sound_cue_sheet(project_id: str, ssots: dict[str, dict[str, Any]], runtime: float) -> dict[str, Any]:
    return {"project_id": project_id, "runtime_s": runtime, "cues": _ssot(ssots, "audio")["cues"]}
