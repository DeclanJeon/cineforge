import json
import shutil
import subprocess

import pytest

from cineforge.edit_plan import EditError, build, validate
from cineforge.subtitles import SubtitleError, to_srt, validate as validate_subs
from closure_fixture import prepared
from cineforge.video_jobs import select_take

FFMPEG = shutil.which('ffmpeg')


def _clip(path, seconds):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=navy:s=192x108:r=12:d={seconds}',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(path)], check=True)


@pytest.mark.skipif(FFMPEG is None, reason='ffmpeg required')
def test_edit_plan_is_deterministic_and_requires_takes(tmp_path):
    project = prepared(tmp_path)
    with pytest.raises(EditError, match='missing_take'):
        build(project.root)
    for cut in project.read('ssot/scene.json')['data']['cuts']:
        _clip(project.root / 'takes' / f'{cut["cut_id"]}.mp4', float(cut['duration']) + 0.2)
        select_take(project.root, cut['cut_id'], f'takes/{cut["cut_id"]}.mp4')
    first = build(project.root)
    second = build(project.root)
    assert first == second
    assert validate(project.root, first) == []
    assert len(first['cuts']) == len(project.read('ssot/scene.json')['data']['cuts'])


def test_subtitles_follow_timing_and_density_rules(tmp_path):
    cues = [{'in': 0.0, 'out': 2.0, 'text': '사진은 좋아해', 'cut_id': 'S01C01'},
            {'in': 2.1, 'out': 4.0, 'text': '근데 이건 네가 찍은 게 아니잖아', 'cut_id': 'S01C02'}]
    path = to_srt(cues, tmp_path / 'subs.srt', runtime=4.0)
    text = path.read_text(encoding='utf-8')
    assert '00:00:00,000 --> 00:00:02,000' in text and '사진은 좋아해' in text
    assert validate_subs(cues, 4.0) == []
    bad = [{'in': 0.0, 'out': 0.5, 'text': '짧음', 'cut_id': 'x'},
           {'in': 0.2, 'out': 3.0, 'text': '겹침', 'cut_id': 'y'},
           {'in': 3.0, 'out': 3.4, 'text': 'a' * 60, 'cut_id': 'z'}]
    issues = validate_subs(bad, 4.0)
    assert any(item.startswith('too_short') for item in issues)
    assert any(item.startswith('overlap') for item in issues)
    assert any(item.startswith('too_dense') for item in issues)
    with pytest.raises(SubtitleError):
        to_srt(bad, tmp_path / 'bad.srt', runtime=4.0)


def test_edit_plan_rejects_short_take(tmp_path):
    project = prepared(tmp_path)
    cut = project.read('ssot/scene.json')['data']['cuts'][0]
    registry = {'takes': [{'take_id': 'X', 'cut_id': cut['cut_id'], 'status': 'available',
                           'path': 'takes/x.mp4', 'duration': 0.1}]}
    (project.root / 'takes').mkdir(exist_ok=True)
    (project.root / 'takes/take_registry.json').write_text(json.dumps(registry))
    with pytest.raises(EditError, match='take_too_short'):
        build(project.root)
