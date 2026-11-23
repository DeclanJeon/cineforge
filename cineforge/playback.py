"""Reviewer-reported playback evidence bound to the delivered file.

This records what a person says they watched and heard. It is not the QA gate,
does not promote an asset, and never becomes publication approval.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

VERDICTS = ('pass', 'pass_with_notes', 'needs_revision')
PROVENANCE = 'reviewer_reported'


class PlaybackError(ValueError):
    """The report does not refer to the current delivered file."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _delivery(project: Path) -> dict[str, Any]:
    path = project / 'final/delivery.json'
    if not path.is_file():
        raise PlaybackError('delivery_missing')
    return json.loads(path.read_text(encoding='utf-8'))


def submit(project: Path, report: dict[str, Any], *, rendered: bool = False) -> Path:
    if rendered:
        preview = project / 'edit/render.mp4'
        if not preview.is_file():
            raise PlaybackError('render_missing')
        delivery = {'video': 'edit/render.mp4', 'sha256': _sha(preview)}
    else:
        delivery = _delivery(project)
    video = project / str(delivery['video'])
    if not video.is_file():
        raise PlaybackError('delivered_file_missing')
    for field in ('reviewer', 'observations'):
        if not isinstance(report.get(field), str) or not report[field].strip():
            raise PlaybackError(f'missing_{field}')
    if report.get('verdict') not in VERDICTS:
        raise PlaybackError('invalid_verdict')
    if report.get('watched_entire_video') is not True or report.get('heard_entire_audio') is not True:
        raise PlaybackError('entire_playback_not_attested')
    if report.get('sha256') != delivery['sha256'] or _sha(video) != delivery['sha256']:
        raise PlaybackError('stale_report')
    payload = {'schema_version': 1, 'provenance': PROVENANCE, 'asset': delivery['video'],
               'sha256': delivery['sha256'],
               'report': {key: report[key] for key in ('reviewer', 'verdict', 'observations',
                                                       'watched_entire_video', 'heard_entire_audio')}}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    target = project / 'qa' / ('render-playback.json' if rendered else f'playback-{digest[:16]}.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return target
