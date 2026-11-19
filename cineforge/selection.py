"""S01 콘셉트 선택 — 대화형 질문 흐름 + 비대화형(JSON/플래그/프리셋) 입력 + AI 추천."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Callable

from cineforge.providers.base import Question
from cineforge.providers.router import ProviderRouter
from cineforge.taxonomy import Taxonomy

AskFn = Callable[[str], str]
PrintFn = Callable[[str], None]

# 필수 축의 기본값(AI 판단도 불가할 때의 최종 기본값)
DEFAULTS: dict[str, Any] = {
    "format": "short_drama",
    "genre": ["drama"],
    "narrative": "twist",
    "emotion_arc": ["empathy", "moved"],
    "production_method": "live_action_ai",
    "duration": "s60",
    "aspect": "r9_16",
    "direction": {"texture": "cinematic", "expression": "live_action", "sound": "music_driven"},
}

# 대화형 CLI에서 묻는 자유 입력 항목(판단 요소 중 텍스트로 받는 것)
FREE_TEXT = [
    {"id": "idea", "ko": "한 줄 아이디어/로그라인(없으면 Enter → AI가 작성)", "factor": "plot_concept"},
    {"id": "lead_character", "ko": "주연 캐릭터(이름·설정 또는 캐릭터 파일 경로, 없으면 Enter → AI 설계)", "factor": "lead_character"},
    {"id": "voice", "ko": "목소리/대사 방침(예: 무음성, 내레이션 여성 20대, 없으면 Enter)", "factor": "voice"},
    {"id": "reference", "ko": "레퍼런스 URL/설명(없으면 Enter)", "factor": "reference"},
]

EMPTY: dict[str, Any] = {
    "format": None, "culture_style": None, "era": None, "genre": [], "subgenre": [], "romance_concept": None,
    "world": None, "story_nature": None, "setting": [], "relationship": [], "narrative": None, "direction": {},
    "emotion_arc": [], "visual_aesthetic": None, "production_method": None, "hook": None, "duration": None,
    "aspect": None, "duration_custom_s": None, "overrides": [], "free_text": {}, "sources": {},
}


def new_selection() -> dict[str, Any]:
    return deepcopy(EMPTY)


def merge(base: dict[str, Any], patch: dict[str, Any], source: str) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in patch.items():
        if value in (None, [], {}):
            continue
        if key == "direction":
            for g, v in value.items():
                out["direction"][g] = v
                out["sources"][f"direction.{g}"] = source
        elif key in ("free_text",):
            out["free_text"].update(value)
        elif key == "overrides":
            out["overrides"] = sorted(set(out["overrides"]) | set(value))
        elif key in out or key == "duration_custom_s":
            out[key] = value
            out["sources"][key] = source
    return out


def parse_set_flags(flags: list[str], tax: Taxonomy) -> dict[str, Any]:
    """--set axis=value[,value] / --set direction.texture=cinematic / 한국어 라벨도 허용."""
    patch: dict[str, Any] = {}
    for flag in flags:
        if "=" not in flag:
            raise ValueError(f"--set 형식 오류(axis=value): {flag}")
        key, raw = flag.split("=", 1)
        key = key.strip()
        values = [v.strip() for v in raw.split(",") if v.strip()]
        if key.startswith("direction."):
            group = key.split(".", 1)[1]
            patch.setdefault("direction", {})[group] = tax.resolve("direction", values[0], group).id
            continue
        if key in ("idea", "lead_character", "voice", "reference"):
            patch.setdefault("free_text", {})[key] = raw.strip()
            continue
        if key == "overrides":
            patch["overrides"] = values
            continue
        axis = tax.axis(key)
        ids = [tax.resolve(key, v).id for v in values]
        patch[key] = ids if axis.get("select") in ("many", "arc") else ids[0]
    return patch


def validate(sel: dict[str, Any], tax: Taxonomy) -> list[str]:
    errors: list[str] = []
    for axis_id in tax.order():
        axis = tax.axis(axis_id)
        value = sel.get(axis_id)
        kind = axis.get("select")
        if kind == "per_group":
            for group, item in (value or {}).items():
                if not tax.has(axis_id, item, group):
                    errors.append(f"{axis_id}.{group}: 알 수 없는 항목 {item}")
            continue
        if kind in ("many", "arc"):
            value = value or []
            if len(value) > int(axis.get("max", 99)):
                errors.append(f"{axis_id}: 최대 {axis['max']}개까지 선택")
            for item in value:
                if not tax.has(axis_id, item):
                    errors.append(f"{axis_id}: 알 수 없는 항목 {item}")
            if axis.get("required") and not value:
                errors.append(f"{axis_id}: 필수 선택")
        else:
            if value is None:
                if axis.get("required") and not (axis_id == "duration" and sel.get("duration_custom_s")):
                    errors.append(f"{axis_id}: 필수 선택")
            elif not tax.has(axis_id, value):
                errors.append(f"{axis_id}: 알 수 없는 항목 {value}")
    return errors


def missing_required(sel: dict[str, Any], tax: Taxonomy) -> list[str]:
    out = []
    for axis_id in tax.order():
        axis = tax.axis(axis_id)
        if not axis.get("required"):
            continue
        value = sel.get(axis_id)
        if axis.get("select") == "per_group":
            if not value:
                out.append(axis_id)
        elif value in (None, []):
            if axis_id == "duration" and sel.get("duration_custom_s"):
                continue
            out.append(axis_id)
    return out


def recommend(axis_id: str, sel: dict[str, Any], request: str, router: ProviderRouter, tax: Taxonomy,
              group: str | None = None) -> str:
    """AI 추천: Jev Choice(가능하면) → 휴리스틱(기본값)."""
    items = tax.items(axis_id, group)
    criteria = {i.id: i.ko + (f" — {i.data['desc']}" if i.data.get("desc") else "") for i in items}
    default = DEFAULTS.get(axis_id)
    if axis_id == "direction":
        default = DEFAULTS["direction"].get(group or "")
    if isinstance(default, list):
        default = default[0]
    if default not in criteria:
        default = items[0].id
    q = Question(f"recommend_{axis_id}{'_' + group if group else ''}", "choice",
                 f"요청과 지금까지의 선택을 보고 '{tax.axis(axis_id)['ko']}{(' / ' + group) if group else ''}'에 가장 어울리는 항목은?",
                 criteria, hints={"default": default, "keywords": {i.id: [i.ko] for i in items}})
    state = {"request": request, "selection": {k: v for k, v in sel.items() if k not in ("sources",)}}
    answer = router.decide(state, [q], task=q.id)[q.id]
    return str(answer.value)


def fill_required(sel: dict[str, Any], request: str, router: ProviderRouter, tax: Taxonomy) -> dict[str, Any]:
    """비대화형 모드: 남은 필수 축을 AI 추천(또는 기본값)으로 채운다. 출처는 'ai'로 기록."""
    out = deepcopy(sel)
    for axis_id in missing_required(out, tax):
        axis = tax.axis(axis_id)
        if axis.get("select") == "per_group":
            for group in ("texture", "expression", "sound"):
                if group not in out["direction"]:
                    out["direction"][group] = recommend(axis_id, out, request, router, tax, group)
                    out["sources"][f"direction.{group}"] = "ai"
            continue
        choice = recommend(axis_id, out, request, router, tax)
        out[axis_id] = [choice] if axis.get("select") in ("many", "arc") else choice
        if axis_id == "emotion_arc" and choice in DEFAULTS["emotion_arc"]:
            out[axis_id] = list(DEFAULTS["emotion_arc"])
        out["sources"][axis_id] = "ai"
    return out


def _render_options(tax: Taxonomy, axis_id: str, group: str | None, printer: PrintFn) -> list[str]:
    axis = tax.axis(axis_id)
    ids: list[str] = []
    for g in axis["groups"]:
        if group and g["id"] != group:
            continue
        printer(f"  [{g['ko']}]")
        line: list[str] = []
        for item in tax.items(axis_id, g["id"]):
            ids.append(item.id)
            line.append(f"{len(ids):>3}) {item.ko}")
            if len(line) == 4:
                printer("   " + "  ".join(line))
                line = []
        if line:
            printer("   " + "  ".join(line))
    return ids


def _parse_answer(raw: str, ids: list[str], tax: Taxonomy, axis_id: str, group: str | None) -> list[str]:
    out: list[str] = []
    for token in [t.strip() for t in raw.replace("→", ",").replace(">", ",").split(",") if t.strip()]:
        if token.isdigit() and 1 <= int(token) <= len(ids):
            out.append(ids[int(token) - 1])
        else:
            out.append(tax.resolve(axis_id, token, group).id)
    return out


def interactive(sel: dict[str, Any], request: str, router: ProviderRouter, tax: Taxonomy,
                ask: AskFn = input, printer: PrintFn = print, confirm_detected: bool = False) -> dict[str, Any]:
    """대화형 선택. 입력 규칙: 번호/라벨(여러 개는 쉼표), Enter=기본값/건너뛰기, ?=AI 추천, !=AI에게 남은 항목 전부 맡기기."""
    out = deepcopy(sel)
    printer("\n=== 콘셉트 설계기 — 모든 선택을 지금 끝내면 이후 제작은 논스톱으로 진행됩니다 ===")
    printer("입력: 번호/이름(복수는 쉼표·화살표), Enter=건너뛰기(필수는 기본값), ?=AI 추천, !=남은 항목 모두 AI에 맡기기\n")
    delegate_rest = False
    for axis_id in tax.order():
        axis = tax.axis(axis_id)
        groups = [g["id"] for g in axis["groups"]] if axis.get("select") == "per_group" else [None]
        for group in groups:
            current = out["direction"].get(group) if group else out.get(axis_id)
            label = axis["ko"] + (f" › {next(g['ko'] for g in axis['groups'] if g['id'] == group)}" if group else "")
            if current not in (None, []) and not confirm_detected:
                continue
            if delegate_rest:
                if axis.get("required") and current in (None, []) and (group is None or group in DEFAULTS["direction"]):
                    out = fill_required(out, request, router, tax)
                continue
            printer(f"\n■ {label}{' (필수)' if axis.get('required') else ''}"
                    f"{' — 최대 ' + str(axis['max']) + '개' if axis.get('max') else ''}"
                    f"{' — 순서대로 감정 곡선' if axis.get('select') == 'arc' else ''}")
            ids = _render_options(tax, axis_id, group, printer)
            while True:
                raw = ask(f"  선택 [{current or '없음'}]: ").strip()
                if raw == "!":
                    delegate_rest = True
                    out = fill_required(out, request, router, tax)
                    break
                if raw == "?":
                    rec = recommend(axis_id, out, request, router, tax, group)
                    printer(f"  → AI 추천: {tax.get(axis_id, rec, group).ko}")
                    raw = ask("  추천을 쓰려면 Enter, 아니면 직접 입력: ").strip() or rec
                if not raw:
                    if axis.get("required") and current in (None, []):
                        if group and group not in DEFAULTS["direction"]:
                            break
                        out = fill_required(out, request, router, tax)
                    break
                try:
                    chosen = _parse_answer(raw, ids, tax, axis_id, group)
                except KeyError as exc:
                    printer(f"  ! {exc}")
                    continue
                if group:
                    out["direction"][group] = chosen[0]
                    out["sources"][f"direction.{group}"] = "user"
                elif axis.get("select") in ("many", "arc"):
                    out[axis_id] = chosen[: int(axis.get("max", 3))]
                    out["sources"][axis_id] = "user"
                else:
                    out[axis_id] = chosen[0]
                    out["sources"][axis_id] = "user"
                break
    if not delegate_rest:
        printer("\n■ 추가 정보")
        for field in FREE_TEXT:
            if out["free_text"].get(field["id"]):
                continue
            value = ask(f"  {field['ko']}: ").strip()
            if value:
                out["free_text"][field["id"]] = value
    return out


def summarize(sel: dict[str, Any], tax: Taxonomy) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for axis_id in tax.order():
        axis = tax.axis(axis_id)
        value = sel.get(axis_id)
        if axis.get("select") == "per_group":
            for g in axis["groups"]:
                if g["id"] in (value or {}):
                    rows.append((f"{axis['ko']} › {g['ko']}", tax.get(axis_id, value[g["id"]], g["id"]).ko,
                                 sel["sources"].get(f"direction.{g['id']}", "-")))
            continue
        if value in (None, []):
            continue
        labels = tax.labels(axis_id, value if isinstance(value, list) else [value])
        joiner = " → " if axis.get("select") == "arc" else ", "
        rows.append((axis["ko"], joiner.join(labels), sel["sources"].get(axis_id, "-")))
    return rows


def load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
