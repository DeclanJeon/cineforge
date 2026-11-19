"""기획안 Markdown 렌더러 — 사용자 예시(《면접관이 제 전 여친입니다》)와 같은 7개 절 구성."""
from __future__ import annotations

from typing import Any


def _ts(seconds: float) -> str:
    s = int(round(float(seconds)))
    return f"{s // 60:02d}:{s % 60:02d}"


def _sec(x: float) -> str:
    x = float(x)
    return f"{x:g}초"


def plan_markdown(plan: dict[str, Any], concept: dict[str, Any] | None = None) -> str:
    m = plan["meta"]
    lines = [f"# {m['runtime_s']:g}초 {m.get('style', '')} 기획안".strip(), "", "제작 기획안 v" + str(plan.get("version", "1.0")), "",
             f"- 화면비: {m['aspect']}", f"- 서사 구조: {m['narrative']}", "", f"## {plan['title']}", "", f"> {plan['logline']}", "",
             "| 항목 | 내용 |", "|---|---|",
             f"| 장르 | {' · '.join(m['genres'])} |",
             f"| 러닝타임 | {m['runtime_s']:g}초 / {m['scene_count']}개 씬 / {m['cut_count']}개 컷 |",
             f"| 영상 스타일 | {m['style']} |", f"| 핵심 전략 | {m['strategy']} |"]
    if concept:
        c = concept["concept"]
        lines += [f"| 조합 콘셉트 | {c.get('chain', '')} |", f"| 감정 곡선 | {c.get('emotion_arc', '')} |",
                  f"| 평가 점수 | {concept['evaluation']['total']} ({concept['evaluation']['verdict']}) |"]
    lines += ["", "## 1. 시놉시스", "", plan["synopsis"], "", "## 2. 후킹 전략", "",
              f"**{_ts(plan['hook']['start'])}–{_ts(plan['hook']['end'])} · Cold Open**", ""]
    if plan["hook"].get("line"):
        lines += [f"“{plan['hook']['line']}”", ""]
    lines += [plan["hook"]["visual"], "", f"화면 자막: {plan['hook']['caption']}", "", "시청자가 품게 될 질문:"]
    lines += [f"- {q}" for q in plan["hook"]["questions"]]
    lines += ["", "## 3. 전체 타임라인", "", "| 구간 | 씬 | 내용 | 요약 |", "|---|---|---|---|"]
    for t in plan["timeline"]:
        lines.append(f"| {_ts(t['start'])}–{_ts(t['end'])} | {t['scene_no']} | {t['label']} | {t.get('summary', '')} |")
    lines += ["", "## 4. 씬별 상세 콘티 및 컷 구성", ""]
    for s in plan["scenes"]:
        lines += [f"### SCENE {s['no']:02d} — {s['title']}", "", f"{_ts(s['start'])}–{_ts(s['end'])} · 장소: {s['location']}", "",
                  "| 컷 | 길이 | 화면·연출 | 사운드 |", "|---|---|---|---|"]
        for c in s["cuts"]:
            sound = c["sound"]
            if c.get("dialogue"):
                sound = f"“{c['dialogue']}”" + (f" ({sound})" if sound and sound not in ("대사", "대사 + 앰비언스") else "")
            lines.append(f"| {c['no']:02d} | {_sec(c['duration'])} | {c['visual']} | {sound} |")
        if s.get("direction_note"):
            lines += ["", f"연출 포인트: {s['direction_note']}"]
        lines.append("")
    lines += ["## 5. 캐릭터 설정", ""]
    for ch in plan["characters"]:
        age = f" ({ch['age']})" if ch.get("age") not in (None, "") else ""
        lines += [f"**{ch['name']}{age}** — {ch['role']}", "", f"{ch['persona']}", "", f"- 외형: {ch['appearance']}",
                  f"- 의상: {ch['wardrobe']}", f"- 목소리: {ch.get('voice', '-')}", ""]
    labels = {"aspect": "화면비", "fps": "프레임레이트", "camera": "카메라", "lighting": "조명", "edit": "컷 편집",
              "camera_movement": "카메라 움직임", "bgm": "BGM", "sfx": "효과음", "grading": "컬러 그레이딩", "subtitles": "자막"}
    lines += ["## 6. 촬영·편집·사운드 설계", "", "| 요소 | 제작 지침 |", "|---|---|"]
    lines += [f"| {labels[k]} | {plan['production_spec'][k]} |" for k in labels]
    lines += ["", "## 7. 제작 전 확인할 사항", "", "| ID | 항목 | 상태 | 내용 |", "|---|---|---|---|"]
    for chk in plan.get("preflight_checks", []):
        lines.append(f"| {chk['id']} | {chk['item']} | {chk['status']} | {chk.get('detail', '')}{(' → ' + chk['fix']) if chk.get('fix') else ''} |")
    if plan.get("generated_by") == "mock":
        lines += ["", "> ⚠️ 이 기획안은 오프라인 목(mock) 공급자로 만든 구조 검증용 초안입니다. 실제 창작 내용은 Jev 판단 + 호스트 에이전트/생성 모델로 채웁니다."]
    return "\n".join(lines) + "\n"
