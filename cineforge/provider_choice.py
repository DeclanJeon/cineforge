"""One-time production provider choice per project (approved design: ask at start, with the concept)."""
from __future__ import annotations

from typing import Any, Callable

from . import provider_registry as reg

RELAY = ("이 질문은 에이전트가 대신 답하면 안 됩니다. question.lanes의 용도별 선택지(이름·인증·과금·설치 여부)를 "
         "사용자에게 그대로 보여 주고, 사용자가 고른 것만 기록하세요. 응답: {\"choices\": {용도: 프로바이더id}, "
         "\"user_said\": \"사용자가 실제로 한 말\"}. 고르지 않은 용도는 생략하면 기본값을 씁니다. "
         "미설치 서비스를 고르면 `cineforge services setup <id> --yes`로 모든 에이전트에 등록할 수 있다고 안내하세요.")


def validate(choices: Any) -> dict[str, str]:
    if not isinstance(choices, dict) or not choices:
        raise ValueError("choices_required")
    out: dict[str, str] = {}
    for lane, pid in choices.items():
        if lane not in reg.LANES:
            raise ValueError(f"unknown_lane: {lane}")
        row = reg.get(str(pid))
        if lane not in row["lanes"]:
            raise ValueError(f"provider_not_in_lane: {pid} does not serve {lane}")
        out[lane] = row["id"]
    return out


def apply(inputs: dict[str, Any], choices: dict[str, str], source: str, user_said: str | None = None) -> dict[str, Any]:
    """Merge the choice over defaults into project inputs; the voice lane drives dialogue routing."""
    providers = {**reg.defaults(), **choices}
    inputs["providers"] = providers
    inputs["providers_source"] = source
    if user_said:
        inputs["providers_user_said"] = user_said
    voice = providers.get("voice")
    if voice in ("typecast", "fish-audio", "fish_audio"):
        inputs["external_voice"] = True
        inputs["voice_provider"] = "fish_audio" if voice.startswith("fish") else voice
    elif voice and voice != "native-audio":
        inputs["external_voice"] = True
        inputs["voice_provider"] = voice
    return inputs


def request(available: dict[str, bool] | None = None) -> dict[str, Any]:
    return {"kind": "user_choice", "must_ask_user": True, "instructions": RELAY, "question": reg.question(available)}


def choose_interactive(ask: Callable[[str], str] = input, printer: Callable[[str], None] = print,
                       available: dict[str, bool] | None = None) -> dict[str, str]:
    """Numbered pick per lane; Enter keeps the default. Installed services are listed first."""
    q = reg.question(available)
    printer("\n=== 제작 서비스 선택 — 용도별로 한 번만 고르면 이후 단계에 반영됩니다 ===")
    printer("입력: 번호 또는 id, Enter=기본값. ✓ 표시는 이미 에이전트에 등록된 서비스입니다.")
    picked: dict[str, str] = {}
    for lane, block in q["lanes"].items():
        options = block["options"]
        printer(f"\n■ {block['label']} (기본: {block['default']})")
        for n, o in enumerate(options, start=1):
            mark = "✓" if o["available"] else " "
            printer(f"  {n:>2}. {mark} {o['name']} [{o['id']}] · {o['auth']} · {o['billing']}")
        while True:
            raw = ask(f"  선택 [{block['default']}]: ").strip()
            if not raw:
                picked[lane] = block["default"]
                break
            ids = [o["id"] for o in options]
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                picked[lane] = ids[int(raw) - 1]
                break
            if raw in ids:
                picked[lane] = raw
                break
            printer("  목록의 번호나 id를 입력하세요.")
    return picked
