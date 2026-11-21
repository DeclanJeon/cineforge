import json
from pathlib import Path
import shutil

import pytest

from cineforge.local_motion import compile_plan, deliver, render


def plan(recipe):
    data = {'headline': 'Changes? 100%'}
    if recipe == 'ui_state':
        data.update(option='Select', reply='Agreed', select_frame=6, reply_frame=15)
    else:
        data.update(detail="Let's try: again")
    return {'meta':{'runtime_s':2}, 'production_spec':{'aspect':'9:16', 'motion_recipe':{'recipe':recipe}},
            'scenes':[{'start':0,'end':2,'cuts':[{'duration':2,'motion':data}]}]}


def test_structured_silence_does_not_create_sound_jobs():
    from cineforge.audio_design import cues_from_plan
    from cineforge.schemas import validate

    assert cues_from_plan([], plan('ui_state'), silent=True) == []
    assert not validate({'project_id': 'demo', 'runtime_s': 2, 'cues': []}, 'sound_cue_sheet')


def test_rejects_early_result_and_audio():
    data = plan('ui_state')
    cut = data['scenes'][0]['cuts'][0]
    cut['motion']['reply_frame'] = 5
    with pytest.raises(ValueError, match='select before replying'):
        compile_plan(data)
    cut['motion']['reply_frame'] = 15
    cut['sound'] = 'approved BGM'
    with pytest.raises(ValueError, match='silent'):
        compile_plan(data)


@pytest.mark.parametrize('recipe', ['ui_state', 'kinetic_type'])
def test_media_and_hash_gate(tmp_path, recipe):
    font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not (font.is_file() and shutil.which('ffmpeg') and shutil.which('ffprobe')):
        pytest.skip('local FFmpeg/fonts unavailable')
    plan_path = tmp_path/'plan.json'
    plan_path.write_text(json.dumps(plan(recipe)))
    report = render(tmp_path, font)
    assert report['frames'] == 60 and report['decode'] == 'pass'
    assert not (tmp_path/'final').exists()
    with pytest.raises(ValueError, match='hash mismatch'):
        deliver(tmp_path, '0'*64)
    assert deliver(tmp_path, report['sha256'])['human_review']
    plan_path.write_text(plan_path.read_text()+'\n')
    with pytest.raises(ValueError, match='hash mismatch'):
        deliver(tmp_path, report['sha256'])
