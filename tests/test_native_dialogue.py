import json
from pathlib import Path

from cineforge.cli import main
from cineforge.jobs import audio_jobs
from cineforge.pipeline import Project

REQ = '15초 코미디 숏드라마, 시네마틱 실사'


def project(tmp_path, *extra):
    main(['new', REQ, '--projects-dir', str(tmp_path), '--project-id', 'p', '--provider', 'mock', '--no-nonstop',
          '--until', 'S03_plan', *extra])
    p = Project(tmp_path / 'p')
    p.grant(accept_plan=True, accept_preproduction=True)
    p.run(until='S07_assets')
    return p


def spoken(p):
    return [r for r in p.read('assets/video_prompts.json')['prompts'] if r['params']['dialogue_mode'] != 'none']


def test_default_dialogue_is_native_in_video_request_and_has_no_tts_job(tmp_path):
    p = project(tmp_path)
    rows = spoken(p)
    assert rows and all(r['params']['dialogue_mode'] == 'native' and r['params']['audio'] for r in rows)
    assert all('AUDIO(네이티브' in r['prompt'] and '목소리' in r['prompt'] for r in rows)
    assert all(r['params']['native_audio_support'] == 'UNVERIFIED' for r in rows)
    sound = p.read('assets/sound_plan.json')['cues']
    assert {c['provider'] for c in sound if c['kind'] == 'DIALOGUE'} == {'native'}
    assert 'dialogue' not in {j.kind for j in audio_jobs(p.root)}


def test_external_voice_only_on_explicit_request(tmp_path):
    p = project(tmp_path, '--external-voice')
    assert all(r['params']['dialogue_mode'] == 'external' and '별도 음성 트랙' in r['prompt'] for r in spoken(p))
    jobs = [j for j in audio_jobs(p.root) if j.kind == 'dialogue']
    assert jobs and all(j.provider == 'fish_audio' for j in jobs)


def test_voice_policy_text_alone_does_not_enable_external_voice(tmp_path):
    p = project(tmp_path, '--voice', '차분한 목소리')
    assert 'dialogue' not in {j.kind for j in audio_jobs(p.root)}


def test_legacy_plan_with_fish_dialogue_is_not_sent_to_tts(tmp_path):
    p = project(tmp_path)
    plan = p.read('assets/sound_plan.json')
    for c in plan['cues']:
        if c['kind'] == 'DIALOGUE':
            c['provider'], c['tool'] = 'fish_audio', 'fish_audio_tts'
    (p.root / 'assets/sound_plan.json').write_text(json.dumps(plan))
    assert 'dialogue' not in {j.kind for j in audio_jobs(p.root)}


def test_silent_and_no_speech_stay_silent(tmp_path):
    p = project(tmp_path, '--no-speech')
    assert all(r['params']['dialogue_mode'] == 'none' and '대사 없음' in r['prompt'] for r in p.read('assets/video_prompts.json')['prompts'])
