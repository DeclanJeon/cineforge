import json
from pathlib import Path
import shutil
import subprocess

import pytest

from cineforge.local_motion import compile_plan, deliver, render


def plan(recipe):
    data = {'headline': 'Changes? 100%'}
    if recipe == 'ui_state':
        data.update(option='Select', reply='Agreed', select_frame=6, reply_frame=15)
    elif recipe == 'diagram_data':
        data.update(steps=['Ready', 'Check', 'Done'], reveal_frames=[0, 12, 24])
    elif recipe == 'card_sequence':
        data.update(layout='compare', cards=['Alpha', 'Beta'], reveal_frames=[0, 15])
    elif recipe == 'shape_morph':
        data.update(detail='Result', from_shape='square', to_shape='circle', morph_start_frame=5, morph_end_frame=26)
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


def test_step_diagram_holds_complete_sequence_and_refuses_chart_data():
    data = plan('diagram_data')
    motion = data['scenes'][0]['cuts'][0]['motion']
    assert compile_plan(data)[0] == 'diagram_data'
    for invalid in ([0, 12, 12], [0, 12, 31], [0, 12], [True, 12, 24]):
        motion['reveal_frames'] = invalid
        with pytest.raises(ValueError, match='diagram'):
            compile_plan(data)
    motion['reveal_frames'] = [0, 12, 24]
    motion['values'] = [4, 7, 12]
    with pytest.raises(ValueError, match='invalid motion text fields'):
        compile_plan(data)


def test_shape_morph_keeps_an_anchor_and_holds_result():
    from cineforge.local_motion import shape_tile

    data = plan('shape_morph')
    cut = data['scenes'][0]['cuts'][0]['motion']
    assert compile_plan(data)[0] == 'shape_morph'
    before, during, after = [shape_tile(cut, n) for n in (4, 16, 27)]
    assert len({before, during, after}) == 3
    center = (100 * 200 + 100) * 3
    assert before[center:center+3] == during[center:center+3] == after[center:center+3]
    assert before[:3] != after[:3]
    cut['morph_end_frame'] = 31
    with pytest.raises(ValueError, match='hold'):
        compile_plan(data)
    cut['morph_end_frame'] = 26
    cut['to_shape'] = 'square'
    with pytest.raises(ValueError, match='distinct'):
        compile_plan(data)


def test_wipe_does_not_cover_first_required_event():
    data = plan('ui_state')
    motion = data['scenes'][0]['cuts'][0]['motion']
    motion['entrance'] = {'kind':'wipe_left','duration_frames':6}
    assert compile_plan(data)[1][0][1]['entrance']['kind'] == 'wipe_left'
    motion['entrance']['duration_frames'] = 7
    with pytest.raises(ValueError, match='before the first action'):
        compile_plan(data)
    motion['entrance']['duration_frames'] = 31
    with pytest.raises(ValueError, match='hold'):
        compile_plan(data)


def test_card_contract_requires_comparable_count_and_reading_time():
    data = plan('card_sequence')
    motion = data['scenes'][0]['cuts'][0]['motion']
    assert compile_plan(data)[0] == 'card_sequence'
    motion.update(cards=['Alpha', 'Beta','Gamma'], reveal_frames=[0, 12, 24])
    with pytest.raises(ValueError, match='comparison'):
        compile_plan(data)
    motion['layout'] = 'carousel'
    with pytest.raises(ValueError, match='card reading hold'):
        compile_plan(data)


def test_image_reveal_requires_a_hashed_project_asset(tmp_path):
    import subprocess as sp
    from cineforge.local_motion import render

    font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not (font.is_file() and shutil.which('ffmpeg')):
        pytest.skip('local FFmpeg/fonts unavailable')
    spec = plan('kinetic_type')
    motion = spec['scenes'][0]['cuts'][0]['motion']
    motion.clear()
    motion.update(headline='Approved mark', asset_id='logo-1', at_frame=9, mode='fade', image_layout='logo')
    spec['production_spec']['motion_recipe'] = {'recipe':'image_reveal','reason':'approved mark reveal'}
    (tmp_path/'assets').mkdir()
    sp.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=0xaa3355:s=300x300','-frames:v','1',str(tmp_path/'assets/logo.png')],check=True)
    (tmp_path/'plan.json').write_text(json.dumps(spec))
    with pytest.raises(ValueError, match='not registered'):
        render(tmp_path, font)
    digest = __import__('hashlib').sha256((tmp_path/'assets/logo.png').read_bytes()).hexdigest()
    (tmp_path/'assets/motion_assets.json').write_text(json.dumps({'assets':{'logo-1':{'path':'assets/logo.png','sha256':digest,'rights':'fixture'}}}))
    assert render(tmp_path, font)['frames'] == 60
    (tmp_path/'assets/logo.png').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        render(tmp_path, font)


def test_chart_requires_source_and_renders_values():
    data = plan('kinetic_type')
    motion = data['scenes'][0]['cuts'][0]['motion']
    motion.clear()
    motion.update(headline='Why the delay', bars=[{'label':'Before','value':20},{'label':'After','value':35}], max_value=40, source='project log 2026-11-21')
    data['production_spec']['motion_recipe'] = {'recipe':'chart_bars','reason':'measured comparison'}
    assert compile_plan(data)[0] == 'chart_bars'
    motion.pop('source')
    with pytest.raises(ValueError, match='recorded source'):
        compile_plan(data)
    motion['source'] = 'fixture'
    motion['bars'][0]['value'] = 41
    with pytest.raises(ValueError, match='recorded source'):
        compile_plan(data)


def test_loop_flag_rejects_mismatched_boundaries(tmp_path):
    font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not (font.is_file() and shutil.which('ffmpeg') and shutil.which('ffprobe')):
        pytest.skip('local FFmpeg/fonts unavailable')
    spec = plan('kinetic_type')
    spec['scenes'][0]['cuts'][0]['motion'].update(loop=True, type_reveal={'phrases':['A','B'],'reveal_frames':[0,12]})
    (tmp_path/'plan.json').write_text(json.dumps(spec))
    with pytest.raises(ValueError, match='do not match'):
        render(tmp_path, font)


def test_poster_presets_are_scoped_and_keep_reading_contrast():
    from cineforge.local_motion import POSTER_PALETTES

    def luminance(hex_color):
        rgb = [int(hex_color[i:i+2], 16)/255 for i in (0,2,4)]
        linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        return sum(v*w for v,w in zip(linear, (.2126,.7152,.0722)))

    for name, (bg, foreground, secondary, _) in POSTER_PALETTES.items():
        data = plan('kinetic_type')
        motion = data['scenes'][0]['cuts'][0]['motion']
        motion['poster'] = name
        assert compile_plan(data)[0] == 'kinetic_type'
        for ink in (foreground, secondary):
            a,b = sorted((luminance(bg),luminance(ink)))
            assert (b+.05)/(a+.05) >= 4.5
    data = plan('ui_state')
    data['scenes'][0]['cuts'][0]['motion']['poster'] = 'editorial'
    with pytest.raises(ValueError, match='poster'):
        compile_plan(data)


def test_type_reveal_preserves_phrase_boundaries_and_reading_hold():
    data = plan('kinetic_type')
    motion = data['scenes'][0]['cuts'][0]['motion']
    motion['type_reveal'] = {'phrases':['한 걸음', '한 번 더', '도착'], 'reveal_frames':[0, 12, 24]}
    assert compile_plan(data)[0] == 'kinetic_type'
    for frames in ([0, 0, 24], [0, 12, 31], [0, True, 24], [0, 12]):
        motion['type_reveal']['reveal_frames'] = frames
        with pytest.raises(ValueError, match='type reveal'):
            compile_plan(data)


def test_connector_and_burst_follow_story_events():
    data = plan('diagram_data')
    motion = data['scenes'][0]['cuts'][0]['motion']
    motion['connector_frames'] = 8
    assert compile_plan(data)[0] == 'diagram_data'
    motion['connector_frames'] = 13
    with pytest.raises(ValueError, match='connector'):
        compile_plan(data)
    ui = plan('ui_state')
    motion = ui['scenes'][0]['cuts'][0]['motion']
    motion['burst'] = {'at_frame': 15, 'seed': 7}
    assert compile_plan(ui)[0] == 'ui_state'
    motion['burst']['at_frame'] = 14
    with pytest.raises(ValueError, match='after the reply'):
        compile_plan(ui)


@pytest.mark.parametrize('recipe', ['ui_state', 'kinetic_type', 'diagram_data', 'shape_morph', 'card_sequence'])
def test_media_and_hash_gate(tmp_path, recipe):
    font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not (font.is_file() and shutil.which('ffmpeg') and shutil.which('ffprobe')):
        pytest.skip('local FFmpeg/fonts unavailable')
    plan_path = tmp_path/'plan.json'
    spec = plan(recipe)
    motion = spec['scenes'][0]['cuts'][0]['motion']
    if recipe == 'kinetic_type':
        motion['entrance'] = {'kind':'wipe_right','duration_frames':12}
    if recipe == 'diagram_data':
        motion['connector_frames'] = 8
    if recipe == 'ui_state':
        motion['burst'] = {'at_frame':15, 'seed':7}
    plan_path.write_text(json.dumps(spec))
    report = render(tmp_path, font)
    assert report['frames'] == 60 and report['decode'] == 'pass'
    if recipe == 'kinetic_type':
        samples = subprocess.check_output([
            'ffmpeg','-v','error','-i',str(tmp_path/report['preview']),
            '-vf',r'select=eq(n\,0)+eq(n\,11)+eq(n\,12),crop=2:2:710:20',
            '-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1',
        ])
        assert len(samples) == 36
        assert samples[0] < 120 and samples[12] < 120 and samples[24] > 200
    if recipe == 'diagram_data':
        decoded = subprocess.check_output([
            'ffmpeg','-v','error','-i',str(tmp_path/report['preview']),
            '-vf',r'select=eq(n\,3)+eq(n\,8)+eq(n\,12),crop=2:2:358:546',
            '-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1',
        ])
        assert len(decoded) == 36
        assert decoded[1] < 60 and decoded[13] > 140 and decoded[25] > 140
    if recipe == 'ui_state':
        decoded = subprocess.check_output([
            'ffmpeg','-v','error','-i',str(tmp_path/report['preview']),
            '-vf',r'select=eq(n\,14)+eq(n\,31)+eq(n\,39),crop=430:320:145:910',
            '-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1',
        ])
        stride = 430*320*3
        assert len(decoded) == 3*stride
        assert max(decoded[:stride]) < 60 and max(decoded[stride:2*stride]) > 140 and max(decoded[2*stride:]) < 60
    assert not (tmp_path/'final').exists()
    with pytest.raises(ValueError, match='hash mismatch'):
        deliver(tmp_path, '0'*64)
    assert deliver(tmp_path, report['sha256'])['human_review']
    plan_path.write_text(plan_path.read_text()+'\n')
    with pytest.raises(ValueError, match='hash mismatch'):
        deliver(tmp_path, report['sha256'])


def test_paper_layers_and_map_route_contracts(tmp_path):
    import subprocess as sp
    from cineforge.local_motion import render

    font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not (font.is_file() and shutil.which('ffmpeg') and shutil.which('ffprobe')):
        pytest.skip('local FFmpeg/fonts unavailable')
    paper = plan('kinetic_type')
    motion = paper['scenes'][0]['cuts'][0]['motion']
    motion.clear()
    motion.update(headline='Paper', layers=['Top', 'Middle'], reveal_frames=[0, 20])
    paper['production_spec']['motion_recipe'] = {'recipe':'paper_layers','reason':'layered cards'}
    (tmp_path/'plan.json').write_text(json.dumps(paper))
    assert render(tmp_path, font)['frames'] == 60
    motion['reveal_frames'] = [0, 45]
    (tmp_path/'plan.json').write_text(json.dumps(paper))
    with pytest.raises(ValueError, match='settled hold'):
        render(tmp_path, font)
    (tmp_path/'assets').mkdir(exist_ok=True)
    sp.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=0xe8e2d5:s=400x400','-frames:v','1',str(tmp_path/'assets/map.png')],check=True)
    digest = __import__('hashlib').sha256((tmp_path/'assets/map.png').read_bytes()).hexdigest()
    (tmp_path/'assets/motion_assets.json').write_text(json.dumps({'assets':{'map':{'path':'assets/map.png','sha256':digest,'rights':'fixture'}}}))
    route = plan('kinetic_type')
    m2 = route['scenes'][0]['cuts'][0]['motion']
    m2.clear()
    m2.update(headline='Route', asset_id='map', route=[[.1,.2],[.5,.6],[.8,.3]], reveal_frames=[10, 25])
    route['production_spec']['motion_recipe'] = {'recipe':'map_route','reason':'supplied map'}
    (tmp_path/'plan.json').write_text(json.dumps(route))
    assert render(tmp_path, font)['frames'] == 60
    m2['route'] = [[.1,.2],[1.2,.6]]
    m2['reveal_frames'] = [10]
    (tmp_path/'plan.json').write_text(json.dumps(route))
    with pytest.raises(ValueError, match='normalized'):
        render(tmp_path, font)


def test_echo_type_and_pose_swap_media(tmp_path):
    import subprocess as sp
    from cineforge.local_motion import render

    font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not (font.is_file() and shutil.which('ffmpeg') and shutil.which('ffprobe')):
        pytest.skip('local FFmpeg/fonts unavailable')
    echo = plan('kinetic_type')
    m = echo['scenes'][0]['cuts'][0]['motion']
    m.clear()
    m.update(headline='Echo', phrases=['One', 'Two', 'Three'], reveal_frames=[0, 10, 20])
    echo['production_spec']['motion_recipe'] = {'recipe':'echo_type','reason':'stacked rhythm'}
    (tmp_path/'plan.json').write_text(json.dumps(echo))
    assert render(tmp_path, font)['frames'] == 60
    m['reveal_frames'] = [0, 10, 50]
    (tmp_path/'plan.json').write_text(json.dumps(echo))
    with pytest.raises(ValueError, match='settled hold'):
        render(tmp_path, font)
    (tmp_path/'assets').mkdir(exist_ok=True)
    for name, colour in (('a.png','0x2244aa'), ('b.png','0xaa4422')):
        sp.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color={colour}:s=300x300','-frames:v','1',str(tmp_path/'assets'/name)],check=True)
    def register():
        ledger = {'assets':{k:{'path':f'assets/{k}.png','sha256':__import__('hashlib').sha256((tmp_path/f'assets/{k}.png').read_bytes()).hexdigest(),'rights':'fixture'} for k in ('a','b')}}
        (tmp_path/'assets/motion_assets.json').write_text(json.dumps(ledger))
    register()
    pose = plan('kinetic_type')
    m2 = pose['scenes'][0]['cuts'][0]['motion']
    m2.clear()
    m2.update(headline='Reaction', poses=['a','b'], at_frame=12)
    pose['production_spec']['motion_recipe'] = {'recipe':'pose_swap','reason':'two supplied poses'}
    (tmp_path/'plan.json').write_text(json.dumps(pose))
    assert render(tmp_path, font)['frames'] == 60
