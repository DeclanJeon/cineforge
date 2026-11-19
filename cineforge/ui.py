"""Terminal presentation: logo, colour policy and the progress panel.

Colour is decoration only. Every line keeps its meaning without ANSI or Unicode
width tricks, so redirects, logs and agent transcripts stay readable.
"""
from __future__ import annotations

import os
import sys
from typing import Any, TextIO

from . import __version__
from .progress import QA_ICON, STATUS_ICON, bar, blockers, next_action, rates

ANSI = {'reset': '\x1b[0m', 'dim': '\x1b[2m', 'accent': '\x1b[38;5;209m', 'good': '\x1b[32m',
        'warn': '\x1b[33m', 'bad': '\x1b[31m', 'muted': '\x1b[38;5;245m'}

ART = (
    '  ██████╗██╗███╗   ██╗███████╗███████╗ ██████╗ ██████╗  ██████╗ ███████╗',
    ' ██╔════╝██║████╗  ██║██╔════╝██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝',
    ' ██║     ██║██╔██╗ ██║█████╗  █████╗  ██║   ██║██████╔╝██║  ███╗█████╗  ',
    ' ██║     ██║██║╚██╗██║██╔══╝  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  ',
    ' ╚██████╗██║██║ ╚████║██║     ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗',
    '  ╚═════╝╚═╝╚═╝  ╚═══╝╚═╝     ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝',
)
TAGLINE = '요구사항 한 번, 선택 한 번. 그다음은 논스톱.'


def supports_color(stream: TextIO | None = None) -> bool:
    if os.environ.get('NO_COLOR') or os.environ.get('TERM') == 'dumb':
        return False
    target = stream if stream is not None else sys.stdout
    return bool(getattr(target, 'isatty', lambda: False)())


def colorize(text: str, style: str, *, color: bool) -> str:
    return f'{ANSI.get(style, "")}{text}{ANSI["reset"]}' if color else text


def logo(*, color: bool = False) -> str:
    art = '\n'.join(colorize(line, 'accent', color=color) for line in ART)
    return f'{art}\n  {colorize("CINEFORGE", "good", color=color)}  영상 제작 오케스트레이터'


def banner(version: str = __version__, *, color: bool = False) -> str:
    return f'{logo(color=color)}\n  {colorize(version, "muted", color=color)}  {TAGLINE}'


def panel(progress: dict[str, Any], pipeline: dict[str, Any] | None = None, *, color: bool = False,
          width: int = 30) -> str:
    if pipeline is None:
        from .data_loader import load
        pipeline = load('pipeline.yaml')
    task_rate, progress_rate = rates(progress, pipeline)
    names = {s['id']: s for s in pipeline['stages']}
    stages = list(progress['stages'])
    current = progress.get('current_stage')
    current_meta = next((s for s in pipeline['stages'] if s['id'] == current), {'ko': current or '완료'})
    where = (f"{current} {current_meta['ko']}  ({stages.index(current) + 1}/{len(stages)})"
             if current else '모든 단계 완료')
    head = f"{progress['project_id']}  ·  {where}"
    lines = [colorize(head, 'accent', color=color),
             f"진행률  {bar(progress_rate, width)} {progress_rate:5.1f}%",
             f"작업률  {bar(task_rate, width)} {task_rate:5.1f}%",
             f"다음    {next_action(progress, pipeline)}"]
    lines.append('')
    lines.append(f"{'단계':<24}{'상태':<14}{'작업':>6}  {'검수':<5}담당 스킬")
    for sid, stage in progress['stages'].items():
        meta = names.get(sid, {'ko': sid, 'skills': []})
        tasks = stage.get('tasks') or {}
        done = sum(1 for value in tasks.values() if value == 'done')
        qa = (stage.get('qa') or {}).get('status')
        style = {'done': 'good', 'blocked': 'bad', 'failed': 'bad', 'stale': 'warn',
                 'waiting_user': 'warn', 'waiting_agent': 'warn', 'waiting_external': 'warn'}.get(stage['status'], 'muted')
        label = f"{sid.split('_')[0]:<3} {meta['ko']}"
        row = (f"{label:<24}{STATUS_ICON.get(stage['status'], '?')} {stage['status'][:12]:<12}"
               f"{done:>3}/{len(tasks):<3}{QA_ICON.get(qa, qa):<5}{', '.join(meta.get('skills', []))}")
        lines.append(colorize(row, style, color=color))
        if stage.get('note') and stage['status'] not in ('done', 'pending', 'skipped'):
            lines.append(colorize(f"    └ {stage['note']}", 'muted', color=color))
    found = blockers(progress)
    if found:
        lines.append('')
        lines.extend(colorize(f'멈춤: {row}', 'bad', color=color) for row in found)
    return '\n'.join(lines)
