import json
import shutil
import subprocess

import pytest

from cineforge.audio_jobs import apply_results, plan_jobs, require_lanes
from cineforge.video_jobs import select_take
from closure_fixture import prepared

FFMPEG = shutil.which('ffmpeg')


def _wav(path, seconds=0.5):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}',
                    '-y', str(path)], check=True)


def _mp4(path, seconds=1.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=navy:s=192x108:r=12:d={seconds}',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(path)], check=True)


def test_audio_jobs_are_refused_without_execution(tmp_path):
    project = prepared(tmp_path)
    assert plan_jobs(project.root)
    with pytest.raises(Exception, match='execution_not_authorized'):
        require_lanes(project.root)


def test_audio_results_register_files_and_isolate_failures(tmp_path):
    project = prepared(tmp_path)
    project.grant(execution=True, providers=['suno', 'elevenlabs', 'fish_audio', 'ludyte'])
    jobs = plan_jobs(project.root)[:2]
    first, second = jobs
    out = project.root / 'audio/renders' / 'first.wav'
    _wav(out)
    registry = apply_results(project.root, [
        {'job_id': first.job_id, 'status': 'accepted', 'path': 'audio/renders/first.wav'},
        {'job_id': second.job_id, 'status': 'rejected', 'error': 'policy'}])
    rows = {row['cue_id']: row for row in registry['cues']}
    assert rows[first.job_id.split(':')[1]]['status'] == 'available'
    assert rows[first.job_id.split(':')[1]]['sha256']
    assert rows[second.job_id.split(':')[1]]['status'] == 'rejected'


@pytest.mark.skipif(FFMPEG is None, reason='ffmpeg required')
def test_select_take_checks_length_and_keeps_history(tmp_path):
    project = prepared(tmp_path)
    cut_id = project.read('ssot/scene.json')['data']['cuts'][0]['cut_id']
    need = float(project.read('ssot/scene.json')['data']['cuts'][0]['duration']) + 0.2
    _mp4(project.root / 'takes' / 'good.mp4', need)
    first = select_take(project.root, cut_id, 'takes/good.mp4')
    _mp4(project.root / 'takes' / 'short.mp4', 0.1)
    with pytest.raises(Exception, match='take_too_short'):
        select_take(project.root, cut_id, 'takes/short.mp4')
    _mp4(project.root / 'takes' / 'second.mp4', need)
    second = select_take(project.root, cut_id, 'takes/second.mp4')
    registry = json.loads((project.root / 'takes/take_registry.json').read_text())['takes']
    assert first['status'] in ('available', 'superseded')
    assert second['take_id'].endswith('T2')
    assert [row['status'] for row in registry if row['cut_id'] == cut_id] == ['superseded', 'available']
