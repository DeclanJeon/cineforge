import hashlib
import json
from pathlib import Path

import pytest

from cineforge.cli import main
from cineforge.playback import PlaybackError, submit
from cineforge.skills import check
from conftest import make_skill_pack


def _delivery(tmp_path):
    root = tmp_path / 'p'
    (root / 'final').mkdir(parents=True)
    video = b'mp4-bytes'
    (root / 'final/p.mp4').write_bytes(video)
    digest = hashlib.sha256(video).hexdigest()
    (root / 'final/delivery.json').write_text(json.dumps({'video': 'final/p.mp4', 'sha256': digest}))
    return root, digest


def test_playback_report_is_bound_to_delivered_hash(tmp_path):
    root, digest = _delivery(tmp_path)
    report = {'sha256': digest, 'reviewer': '검수자', 'verdict': 'pass', 'observations': '전체 확인',
              'watched_entire_video': True, 'heard_entire_audio': True}
    path = submit(root, report)
    saved = json.loads(path.read_text())
    assert saved['provenance'] == 'reviewer_reported' and saved['sha256'] == digest
    assert submit(root, report) == path
    stale = dict(report, sha256='0' * 64)
    with pytest.raises(PlaybackError, match='stale_report'):
        submit(root, stale)
    with pytest.raises(PlaybackError, match='entire_playback_not_attested'):
        submit(root, {**report, 'heard_entire_audio': False})
    (root / 'final/p.mp4').write_bytes(b'changed')
    with pytest.raises(PlaybackError, match='stale_report'):
        submit(root, report)


def test_playback_cli_requires_delivery_and_valid_report(tmp_path, capsys):
    root, digest = _delivery(tmp_path)
    payload = tmp_path / 'report.json'
    payload.write_text(json.dumps({'sha256': digest, 'reviewer': 'r', 'verdict': 'needs_revision',
                                    'observations': '2초 지점 흔들림', 'watched_entire_video': True,
                                    'heard_entire_audio': True}))
    assert main(['qa-playback', str(root), '--file', str(payload)]) == 0
    capsys.readouterr()
    missing = tmp_path / 'empty'
    missing.mkdir()
    assert main(['qa-playback', str(missing), '--file', str(payload)]) == 1


def test_skill_pack_check_reports_missing_and_pins(tmp_path):
    report = check(tmp_path / 'none')
    assert report['available'] is False and report['status'] == 'missing'
    pack = make_skill_pack(tmp_path / 'pack')
    report = check(pack)
    assert report['available'] is True and report['status'] == 'ready'
    assert report['pins']['creative-production/SKILL.md'] == hashlib.sha256(b'fixture').hexdigest()


def test_skills_cli_exit_codes(tmp_path, capsys):
    assert main(['skills', '--root', str(tmp_path / 'none')]) == 1
    pack = make_skill_pack(tmp_path / 'pack')
    capsys.readouterr()
    assert main(['skills', '--root', str(pack)]) == 0
    assert json.loads(capsys.readouterr().out)['available'] is True
