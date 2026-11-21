import json
import shutil
import subprocess

import pytest

from cineforge.assembly import AssemblyError, loudness, probe, render
from cineforge.edit_plan import build
from cineforge.video_jobs import select_take
from closure_fixture import prepared

FFMPEG = shutil.which('ffmpeg')


def _clip(path, seconds, color='navy'):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c={color}:s=192x108:r=24:d={seconds}',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(path)], check=True)


def _wav(path, seconds):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'sine=frequency=220:duration={seconds}',
                    '-ac', '2', '-ar', '48000', '-y', str(path)], check=True)


@pytest.mark.skipif(FFMPEG is None, reason='ffmpeg required')
def test_render_assembles_real_mp4_with_loudness(tmp_path):
    project = prepared(tmp_path)
    cuts = project.read('ssot/scene.json')['data']['cuts']
    for cut in cuts:
        _clip(project.root / 'takes' / f'{cut["cut_id"]}.mp4', float(cut['duration']) + 0.2)
        select_take(project.root, cut['cut_id'], f'takes/{cut["cut_id"]}.mp4')
    rows = project.read('assets/sound_plan.json')['cues'][:2]
    registry = {'schema_version': 1, 'cues': []}
    for row in rows:
        out = project.root / 'audio' / f'{row["cue_id"]}.wav'
        _wav(out, 1.0)
        registry['cues'].append({'cue_id': row['cue_id'], 'status': 'available', 'path': f'audio/{row["cue_id"]}.wav',
                                 'kind': row['kind']})
    project.write('audio/audio_registry.json', registry)
    plan = build(project.root)
    rendered = render(project.root, plan, output='edit/test-render.mp4', size=(540, 960))
    assert rendered.is_file() and rendered.stat().st_size > 1000
    info = probe(rendered)
    assert info['video_codec'] == 'h264' and info['audio_codec'] == 'aac'
    assert (info['width'], info['height']) == (540, 960)
    assert info['duration'] == pytest.approx(plan['runtime'], abs=0.3)
    measured = loudness(rendered)
    assert -17.0 <= measured['integrated'] <= -11.0
    assert measured['true_peak'] <= 0.0


@pytest.mark.skipif(FFMPEG is None, reason='ffmpeg required')
def test_render_fails_closed_on_missing_cut(tmp_path):
    project = prepared(tmp_path)
    cut = project.read('ssot/scene.json')['data']['cuts'][0]
    plan = {'runtime': 3.0, 'fps': 24, 'width': 540, 'height': 960, 'audio': [], 'subtitles': [],
            'cuts': [{'cut_id': cut['cut_id'], 'path': 'takes/none.mp4', 'in': 0, 'out': 1.0}]}
    with pytest.raises(AssemblyError, match='cut_missing'):
        render(project.root, plan, size=(180, 320))
