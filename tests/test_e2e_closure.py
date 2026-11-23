import hashlib
import json
import os
from pathlib import Path
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
@pytest.mark.parametrize("code_motion", [False, True])
def test_request_reaches_delivered_mp4(tmp_path, capsys, monkeypatch, code_motion):
    project = prepared(tmp_path, REQUEST)
    capsys.readouterr()
    project.grant(execution=True, providers=['suno', 'elevenlabs', 'fish_audio', 'ludyte'])
    project.write('edit/proxy.json', {'width': 180, 'height': 320})
    if not code_motion:
        assert main(['execute', str(project.root), '--stage', 'S08_audio']) == 0
    from cineforge.audio_jobs import apply_results, plan_jobs as plan_audio
    wav = project.root / 'audio/tone.wav'
    wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=300:duration=1',
                    '-ac', '2', '-ar', '48000', '-y', str(wav)], check=True)
    results = tmp_path / 'audio-results.json'
    audio_rows = [{'job_id': job.job_id, 'status': 'accepted', 'path': 'audio/tone.wav'} for job in plan_audio(project.root)]
    results.write_text(json.dumps(audio_rows))
    if code_motion:
        apply_results(project.root, audio_rows)  # Pre-existing local audio fixture; no provider execution.
    else:
        assert main(['results', str(project.root), '--stage', 'S08_audio', '--file', str(results)]) == 0
    cuts = project.read('ssot/scene.json')['data']['cuts']
    code_cut = cuts[0]['cut_id'] if code_motion else None
    if code_motion:
        from cineforge import execution_plan
        scope = execution_plan.proposal(project, {'lanes': [{'kind': 'video_cut', 'provider': 'code-motion',
            'model': 'html-seek-v1', 'max_jobs': 1, 'cut_ids': [code_cut]}]})
        execution_plan.approve(project, scope['plan_hash'], 1)
        assert main(['execute', str(project.root), '--stage', 'S08_video']) == 0
    for cut in cuts:
        clip = project.root / 'takes' / f'{cut["cut_id"]}.mp4'
        clip.parent.mkdir(parents=True, exist_ok=True)
        is_code = cut['cut_id'] == code_cut
        source = (f'color=c=orange:s=108x192:r=30:d={cut["duration"]}' if is_code else
                  f'color=c=navy:s=192x108:r=24:d={float(cut["duration"]) + 0.2}')
        pack = os.environ.get('CINEFORGE_TEST_MOTION_PACK') if is_code else None
        if pack:
            html = tmp_path / 'piece.html'
            html.write_text('<meta charset=utf-8><script>window.__motion={width:108,height:192,fps:30,'
                            f'duration:{cut["duration"]},seek(t){{document.body.style.background=t<1?"orange":"gold"}}'
                            '}</script>')
            scripts = Path(pack) / 'video-production-assets/scripts'
            subprocess.run(['node', str(scripts / 'render_html_motion.mjs'), str(html), str(clip)], check=True)
        else:
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', source, '-c:v', 'libx264',
                            '-pix_fmt', 'yuv420p', '-y', str(clip)], check=True)
        if is_code:
            results.write_text(json.dumps([{'job_id': f'video:{code_cut}', 'status': 'accepted',
                                            'path': str(clip.relative_to(project.root))}]))
            assert main(['results', str(project.root), '--stage', 'S08_video', '--file', str(results)]) == 0
        if code_motion:
            assert main(['select-take', str(project.root), '--cut', cut['cut_id'],
                         '--path', str(clip.relative_to(project.root))]) == 0
        else:
            select_take(project.root, cut['cut_id'], f'takes/{cut["cut_id"]}.mp4')
    if not code_motion:
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
    if code_motion:
        assert main(['deliver', str(project.root)]) == 1
        assert 'code_motion_playback_required' in capsys.readouterr().err
        render = project.root / 'edit/render.mp4'
        digest = hashlib.sha256(render.read_bytes()).hexdigest()
        results.write_text(json.dumps({'reviewer': 'test fixture', 'observations': 'simulated reviewer evidence',
            'verdict': 'pass', 'sha256': digest, 'watched_entire_video': True, 'heard_entire_audio': True}))
        assert main(['qa-playback', str(project.root), '--rendered', '--file', str(results)]) == 0
        with render.open('ab') as handle:
            handle.write(b'changed')
        assert main(['deliver', str(project.root)]) == 1
        assert 'code_motion_playback_required' in capsys.readouterr().err
        with render.open('r+b') as handle:
            handle.seek(-len(b'changed'), 2)
            handle.truncate()
    capsys.readouterr()
    assert main(['deliver', str(project.root), '--json']) == 0
    bundle = json.loads(capsys.readouterr().out)
    target = project.root / bundle['video']
    assert target.is_file() and bundle['sha256']
    assert bundle['subtitles'] is None or (project.root / bundle['subtitles']).is_file()
