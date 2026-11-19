"""Dialogue subtitles: SRT sidecar with timing and density rules."""
from __future__ import annotations

from pathlib import Path
from typing import Any

MIN_SECONDS = 1.2
MAX_CHARS = 42
MAX_LINES = 2


class SubtitleError(ValueError):
    """Subtitle cues violate timing or density rules."""


def _stamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}'


def validate(cues: list[dict[str, Any]], runtime: float) -> list[str]:
    issues: list[str] = []
    previous_out = -1.0
    for cue in cues:
        start, end = float(cue['in']), float(cue['out'])
        text = str(cue.get('text') or '').strip()
        if not text:
            issues.append(f'empty_text: {cue.get("cut_id")}')
        if start < 0 or end > runtime + 0.05:
            issues.append(f'out_of_range: {cue.get("cut_id")}')
        if end - start < MIN_SECONDS - 0.01:
            issues.append(f'too_short: {cue.get("cut_id")}')
        if start < previous_out - 0.01:
            issues.append(f'overlap: {cue.get("cut_id")}')
        lines = text.splitlines() or [text]
        if len(lines) > MAX_LINES or any(len(line) > MAX_CHARS for line in lines):
            issues.append(f'too_dense: {cue.get("cut_id")}')
        previous_out = max(previous_out, end)
    return issues


def to_srt(cues: list[dict[str, Any]], target: Path, *, runtime: float | None = None) -> Path:
    issues = validate(cues, runtime if runtime is not None else max((float(cue['out']) for cue in cues), default=0.0))
    if issues:
        raise SubtitleError('; '.join(issues))
    blocks = [f'{index}\n{_stamp(float(cue["in"]))} --> {_stamp(float(cue["out"]))}\n{cue["text"].strip()}\n'
              for index, cue in enumerate(sorted(cues, key=lambda row: float(row['in'])), start=1)]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(blocks), encoding='utf-8')
    return target
