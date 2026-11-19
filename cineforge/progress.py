"""진행 상태 — 작업률(완료 작업/전체 작업)과 진행률(단계 가중치 기반), 검수 상태 표시."""
from __future__ import annotations

from typing import Any

STATUS_ICON = {"done": "✅", "running": "⏳", "pending": "·", "blocked": "⛔", "waiting_user": "🙋", "waiting_agent": "🤖",
               "waiting_external": "🔌", "stale": "♻️", "failed": "❌", "skipped": "⤼"}
QA_ICON = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", None: "-"}


def stage_completion(stage: dict[str, Any]) -> float:
    if stage["status"] in ("done", "skipped"):
        return 1.0
    tasks = stage.get("tasks") or {}
    if not tasks:
        return 0.0
    return sum(1 for v in tasks.values() if v == "done") / len(tasks)


def rates(progress: dict[str, Any], pipeline: dict[str, Any]) -> tuple[float, float]:
    weights = {s["id"]: s["weight"] for s in pipeline["stages"]}
    total_tasks = done_tasks = 0
    wsum = wdone = 0.0
    for sid, stage in progress["stages"].items():
        if stage["status"] == "skipped":  # 건너뛴 단계는 분모에서 제외
            continue
        tasks = stage.get("tasks") or {}
        total_tasks += len(tasks)
        done_tasks += sum(1 for v in tasks.values() if v == "done")
        w = weights.get(sid, 1)
        wsum += w
        wdone += w * stage_completion(stage)
    task_rate = round(100 * done_tasks / total_tasks, 1) if total_tasks else 0.0
    progress_rate = round(100 * wdone / wsum, 1) if wsum else 0.0
    return task_rate, progress_rate


def bar(pct: float, width: int = 24) -> str:
    filled = int(round(width * pct / 100))
    return "█" * filled + "░" * (width - filled)


def render(progress: dict[str, Any], pipeline: dict[str, Any]) -> str:
    task_rate, progress_rate = rates(progress, pipeline)
    names = {s["id"]: s for s in pipeline["stages"]}
    lines = [f"프로젝트 {progress['project_id']} — 현재 단계: {progress.get('current_stage') or '완료'}",
             f"진행률 {bar(progress_rate)} {progress_rate:5.1f}%   (단계 가중치 기준)",
             f"작업률 {bar(task_rate)} {task_rate:5.1f}%   (완료 작업 / 전체 작업)", "",
             f"{'단계':<26}{'상태':<16}{'작업':>5}  {'검수':<6}담당 스킬"]
    for sid, stage in progress["stages"].items():
        meta = names.get(sid, {"ko": sid, "skills": []})
        tasks = stage.get("tasks") or {}
        done = sum(1 for v in tasks.values() if v == "done")
        qa = (stage.get("qa") or {}).get("status")
        icon = STATUS_ICON.get(stage["status"], "?")
        label = f"{sid.split('_')[0]:<3} {meta['ko']}"
        lines.append(f"{label:<26}{icon} {stage['status'][:13]:<14}{done:>3}/{len(tasks):<3}  {QA_ICON.get(qa, qa):<6}{', '.join(meta.get('skills', []))}")
        if stage.get("note") and stage["status"] not in ("done", "pending"):
            lines.append(f"    └ {stage['note']}")
    return "\n".join(lines)
