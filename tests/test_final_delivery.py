import json
import shutil
import subprocess

import pytest

from cineforge.assembly import render
from cineforge.delivery import DeliveryError, deliver
from cineforge.edit_plan import build
from cineforge.final_qa import inspect
from cineforge.gate import promote
from cineforge.video_jobs import select_take
from closure_fixture import prepared

FFMPEG = shutil.which('ffmpeg')


def _clip(path, seconds):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=black:s=192x108:r=24:d={seconds}',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(path)], check=True)


def _ready(tmp_path):
    project = prepared(tmp_path)
    for cut in project.read('ssot/scene.json')['data']['cuts']:
        _clip(project.root / 'takes' / f'{cut["cut_id"]}.mp4', float(cut['duration']) + 0.2)
        select_take(project.root, cut['cut_id'], f'takes/{cut["cut_id"]}.mp4')
    registry = {'schema_version': 1, 'cues': []}
    for cue in project.read('assets/sound_plan.json')['cues'][:1]:
        out = project.root / 'audio' / f'{cue["cue_id"]}.wav'
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=300:duration=1',
                        '-ac', '2', '-ar', '48000', '-y', str(out)], check=True)
        registry['cues'].append({'cue_id': cue['cue_id'], 'status': 'available',
                                 'path': f'audio/{cue["cue_id"]}.wav', 'kind': cue['kind']})
    project.write('audio/audio_registry.json', registry)
    project.write('edit/proxy.json', {'width': 180, 'height': 320})
    plan = build(project.root)
    return project, plan


@pytest.mark.skipif(FFMPEG is None, reason='ffmpeg required')
def test_final_qa_passes_clean_render_and_delivery_writes_bundle(tmp_path):
    project, plan = _ready(tmp_path)
    mp4 = render(project.root, plan, output='edit/render.mp4', size=(180, 320))
    report = inspect(project.root, mp4, plan=plan)
    assert report['status'] == 'fail'  # gate still available-only
    assert any(row['id'] == 'gate' and not row['ok'] for row in report['checks'])
    ids = [row['take_id'] for row in json.loads((project.root / 'takes/take_registry.json').read_text())['takes']]
    promote(project.root, [row['asset_id'] for row in json.loads((project.root / 'assets/asset_registry.json').read_text())['assets']])
    promote(project.root, ids)
    promote(project.root, [row['cue_id'] for row in json.loads((project.root / 'audio/audio_registry.json').read_text())['cues']])
    report = inspect(project.root, mp4, plan=plan)
    assert report['status'] == 'pass', report['checks']
    bundle = deliver(project.root, video=mp4)
    assert (project.root / 'final' / f'{project.root.name}.mp4').is_file()
    assert bundle['sha256'] and bundle['gate']['status'] == 'pass' and bundle['ai_disclosure'] is True


@pytest.mark.skipif(FFMPEG is None, reason='ffmpeg required')
def test_final_qa_fails_on_tampered_duration_and_gate(tmp_path):
    project, plan = _ready(tmp_path)
    mp4 = render(project.root, plan, output='edit/render.mp4', size=(180, 320))
    title = project.root / 'final' / f'{project.root.name}.mp4'
    title.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(mp4, title)
    with pytest.raises(DeliveryError, match='final_qa_failed'):
        deliver(project.root, video=mp4)
    assert not (project.root / 'final/delivery.json').exists()
    long_plan = dict(plan, runtime=plan['runtime'] + 3)
    report = inspect(project.root, mp4, plan=long_plan)
    assert any(row['id'] == 'duration' and not row['ok'] for row in report['checks'])
