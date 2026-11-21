import json
import shutil
import subprocess

import pytest

from cineforge.cli import main
from closure_fixture import prepared
from cineforge.gate import check
from cineforge.video_jobs import select_take

FFMPEG = shutil.which('ffmpeg')
REQUEST = '15초 코미디 숏드라마, 시네마틱 실사'


@pytest.mark.skipif(FFMPEG is None, reason='ffmpeg required')
def test_request_reaches_delivered_mp4(tmp_path, capsys, monkeypatch):
    project = prepared(tmp_path, REQUEST)
    capsys.readouterr()
    project.grant(execution=True, providers=['suno', 'elevenlabs', 'fish_audio', 'ludyte'])
    project.write('edit/proxy.json', {'width': 180, 'height': 320})
    assert main(['execute', str(project.root), '--stage', 'S08_audio']) == 0
    audio = json.loads((project.root / 'jobs/S08_audio.json').read_text())['jobs']
    wav = project.root / 'audio/tone.wav'
    wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=300:duration=1',
                    '-ac', '2', '-ar', '48000', '-y', str(wav)], check=True)
    results = tmp_path / 'audio-results.json'
    results.write_text(json.dumps([{'job_id': job['job_id'], 'status': 'accepted', 'path': 'audio/tone.wav'} for job in audio]))
    assert main(['results', str(project.root), '--stage', 'S08_audio', '--file', str(results)]) == 0
    for cut in project.read('ssot/scene.json')['data']['cuts']:
        clip = project.root / 'takes' / f'{cut["cut_id"]}.mp4'
        clip.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        f'color=c=navy:s=192x108:r=24:d={float(cut["duration"]) + 0.2}', '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p', '-y', str(clip)], check=True)
        select_take(project.root, cut['cut_id'], f'takes/{cut["cut_id"]}.mp4')
    assert main(['execute', str(project.root), '--stage', 'S08_video']) == 0
    assert main(['edit', str(project.root)]) == 0
    assert main(['render', str(project.root)]) == 0
    capsys.readouterr()
    assert check(project.root).status == 'fail'
    assert main(['deliver', str(project.root)]) == 1
    assert main(['gate', str(project.root), '--json']) == 1
    assets = [row['asset_id'] for row in project.read('assets/asset_registry.json')['assets']]
    takes = [row['take_id'] for row in project.read('takes/take_registry.json')['takes']]
    cues = [row['cue_id'] for row in project.read('audio/audio_registry.json')['cues'] if row.get('status') == 'available']
    assert assets and takes and cues
    monkeypatch.setattr('sys.stdin.isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda prompt='': 'VERIFY')
    assert main(['verify', str(project.root), '--all', '--attest', '파일 확인']) == 0
    assert check(project.root).status == 'pass'
    assert main(['qa-final', str(project.root), '--json']) == 0
    capsys.readouterr()
    assert main(['deliver', str(project.root), '--json']) == 0
    bundle = json.loads(capsys.readouterr().out)
    target = project.root / bundle['video']
    assert target.is_file() and bundle['sha256']
    assert bundle['subtitles'] is None or (project.root / bundle['subtitles']).is_file()
