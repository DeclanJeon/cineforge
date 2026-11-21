"""Final QA for the assembled film: fail closed, never a soft warning."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from .assembly import loudness, probe
from .gate import check as gate_check
from .subtitles import validate as subtitle_issues


class FinalQAError(RuntimeError):
    """The delivered file cannot be certified."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(project: Path, video: Path, *, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    plan = plan or json.loads((project / 'edit/edit_plan.json').read_text(encoding='utf-8'))
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = '') -> None:
        checks.append({'id': name, 'ok': ok, 'detail': detail})

    add('file', video.is_file(), str(video))
    if not video.is_file():
        return _finish(project, checks)
    info = probe(video)
    expected = float(plan['runtime'])
    add('duration', abs(info['duration'] - expected) <= 0.25, f"{info['duration']:.2f}s vs {expected:.2f}s")
    add('video_codec', info['video_codec'] == 'h264', str(info['video_codec']))
    add('audio_codec', info['audio_codec'] == 'aac', str(info['audio_codec']))
    add('size', (info['width'], info['height']) == (int(plan['width']), int(plan['height'])),
        f"{info['width']}x{info['height']}")
    decode = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(video), '-f', 'null', '-'],
                            capture_output=True, text=True)
    add('decode', decode.returncode == 0 and not decode.stderr.strip(), decode.stderr.strip()[:160])
    measured = loudness(video)
    add('loudness', -15.0 <= measured['integrated'] <= -13.0, f"{measured['integrated']:.2f} LUFS")
    add('true_peak', measured['true_peak'] <= -0.9, f"{measured['true_peak']:.2f} dBTP")
    subtitles = plan.get('subtitles') or []
    issues = subtitle_issues(subtitles, expected) if subtitles else []
    add('subtitles', not issues, '; '.join(issues[:3]))
    gate = gate_check(project)
    add('gate', gate.status == 'pass', f"{len(gate.blockers)} blockers")
    report = _finish(project, checks, video=video)
    return report


def _finish(project: Path, checks: list[dict[str, Any]], *, video: Path | None = None) -> dict[str, Any]:
    status = 'pass' if checks and all(row['ok'] for row in checks) else 'fail'
    report = {'schema_version': 1, 'status': status, 'checks': checks,
              'sha256': _sha(video) if video and video.is_file() else None}
    path = project / 'qa/final_report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report
