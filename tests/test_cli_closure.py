import json
import shutil
import subprocess

import pytest

from cineforge.cli import main
from closure_fixture import prepared
from cineforge.video_jobs import select_take

FFMPEG = shutil.which('ffmpeg')


def _clip(path, seconds):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=navy:s=192x108:r=24:d={seconds}',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(path)], check=True)


def test_execute_requires_approval_then_writes_envelope(tmp_path, capsys):
    project = prepared(tmp_path)
    capsys.readouterr()
    assert main(['execute', str(project.root), '--stage', 'S08_audio']) == 1
    project.grant(execution=True, providers=['suno', 'elevenlabs', 'fish_audio', 'ludyte'])
    assert main(['execute', str(project.root), '--stage', 'S08_audio']) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['jobs'] > 0 and (project.root / payload['envelope']).is_file()


def test_results_and_edit_commands(tmp_path, capsys):
    if FFMPEG is None:
        pytest.skip('ffmpeg required')
    project = prepared(tmp_path)
    project.grant(execution=True, providers=['suno', 'elevenlabs', 'fish_audio', 'ludyte'])
    capsys.readouterr()
    assert main(['execute', str(project.root), '--stage', 'S08_audio']) == 0
    capsys.readouterr()
    envelope = json.loads((project.root / 'jobs/S08_audio.json').read_text())
    job = envelope['jobs'][0]
    out = project.root / 'audio/x.wav'
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=300:duration=1',
                    '-ac', '2', '-ar', '48000', '-y', str(out)], check=True)
    results = tmp_path / 'results.json'
    results.write_text(json.dumps([{'job_id': job['job_id'], 'status': 'accepted', 'path': 'audio/x.wav'}]))
    assert main(['results', str(project.root), '--stage', 'S08_audio', '--file', str(results)]) == 0
    capsys.readouterr()
    for cut in project.read('ssot/scene.json')['data']['cuts']:
        _clip(project.root / 'takes' / f'{cut["cut_id"]}.mp4', float(cut['duration']) + 0.2)
        select_take(project.root, cut['cut_id'], f'takes/{cut["cut_id"]}.mp4')
    project.write('edit/proxy.json', {'width': 180, 'height': 320})
    assert main(['edit', str(project.root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['cuts'] > 0 and payload['plan'].endswith('edit/edit_plan.json')
