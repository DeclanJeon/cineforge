import json
import os
import stat
from pathlib import Path

import pytest

from cineforge.cli import main
from cineforge.sound import (KEYS, MCP_SERVERS, SetupError, SoundError, apply, credentials_path, plan, remove_key,
                             set_key, status, write_plan)


def cues():
    return [
        {'type': 'BGM', 'tc_in': 0.0, 'tc_out': 8.0, 'description': '전시실 첫 대면', 'cue_id': 'Q001'},
        {'type': 'SFX', 'tc_in': 2.5, 'tc_out': 3.1, 'description': '액자 유리 긁히는 소리', 'cue_id': 'Q002'},
        {'type': 'AMBIENCE', 'tc_in': 0.0, 'tc_out': 8.0, 'description': '사진동 형광등 웅웅', 'cue_id': 'Q003'},
        {'type': 'DIALOGUE', 'tc_in': 3.2, 'tc_out': 5.0, 'description': '서윤: 사진은 좋아해', 'cue_id': 'Q004'},
    ]


def test_plan_routes_each_cue_to_its_mcp_lane():
    rows = plan(cues(), mood='조용한 긴장', era='1999년 한국')
    lanes = {row.kind: (row.provider, row.tool, row.loop) for row in rows}
    assert lanes['BGM'] == ('suno', 'generate_music', True)
    assert lanes['SFX'] == ('elevenlabs', 'elevenlabs_sound_effect', False)
    assert lanes['AMBIENCE'][2] is True
    assert lanes['DIALOGUE'][0] == 'fish_audio'
    assert all(row.prompt.strip() and row.ai_disclosure for row in rows)
    assert 'no vocals' in rows[0].prompt
    with pytest.raises(SoundError, match='unsupported cue type'):
        plan([{'type': 'MIX', 'tc_in': 0, 'tc_out': 1, 'description': 'x', 'cue_id': 'Q1'}], mood='m', era='e')


def test_written_plan_is_an_handoff_not_a_generation(tmp_path):
    payload = write_plan(tmp_path, plan(cues(), mood='m', era='e'), selected={'suno': 'suno'})
    assert payload['generated'] is False
    assert json.loads((tmp_path / 'assets/sound_plan.json').read_text())['cues'][0]['provider'] == 'suno'
    assert all(cue['ai_disclosure'] for cue in payload['cues'])


def test_keys_are_stored_privately_and_never_in_projects(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    path = set_key('elevenlabs', 'sk-eleven-test-123456')
    assert path == credentials_path()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text())[KEYS['elevenlabs']] == 'sk-eleven-test-123456'
    assert status()[2]['key_registered'] is True
    remove_key('elevenlabs')
    assert not json.loads(path.read_text()).get(KEYS['elevenlabs'])
    with pytest.raises(SetupError, match='unknown provider'):
        set_key('nope', 'x' * 12)
    with pytest.raises(SetupError, match='invalid key'):
        set_key('suno', 'short')


def test_setup_lists_every_required_mcp_and_refuses_unconfirmed_install():
    rows = status()
    assert {row['server'] for row in rows} == set(MCP_SERVERS) == {'fish_audio', 'typecast', 'elevenlabs', 'suno'}
    assert all(row['purpose'] for row in rows)
    with pytest.raises(SetupError, match='confirmation_required'):
        apply(['suno'], yes=False)
    with pytest.raises(SetupError, match='unknown server'):
        apply(['nope'], yes=True)


def test_setup_runs_only_declared_recipes(tmp_path):
    calls = []

    def runner(command):
        calls.append(command)

    with pytest.raises(SetupError, match='install_recipe_unknown'):
        apply(['suno'], yes=True, runner=runner)
    done = apply(['suno', 'elevenlabs'], yes=True, runner=runner,
                 recipes={'suno': ['mcp', 'install', 'suno'], 'elevenlabs': ['mcp', 'install', 'elevenlabs']})
    assert done == ['suno', 'elevenlabs']
    assert calls == [['mcp', 'install', 'suno'], ['mcp', 'install', 'elevenlabs']]


def test_cli_set_key_uses_hidden_input_and_never_prints_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'cfg'))
    monkeypatch.setattr('getpass.getpass', lambda prompt='': 'sk-suno-test-abcdef')
    assert main(['setup', '--set-key', 'suno']) == 0
    out = capsys.readouterr().out
    assert 'sk-suno-test-abcdef' not in out
    assert '등록' in out
    config = tmp_path / 'cfg' / 'cineforge' / 'credentials.json'
    assert oct(stat.S_IMODE(config.stat().st_mode)) == '0o600'


def test_pipeline_writes_provider_addressed_sound_plan(tmp_path):
    from conftest import SAMPLE_REQUEST
    main(['new', SAMPLE_REQUEST, '--projects-dir', str(tmp_path), '--project-id', 's', '--provider', 'mock',
          '--no-nonstop', '--until', 'S03_plan'])
    from cineforge.pipeline import Project
    project = Project(tmp_path / 's')
    project.grant(accept_plan=True, accept_preproduction=True)
    project.run(until='S07_assets')
    sound = project.read('assets/sound_plan.json')
    assert sound and sound['generated'] is False
    assert {cue['provider'] for cue in sound['cues']} <= {'suno', 'elevenlabs', 'fish_audio'}
    assert all(cue['tool'] and cue['prompt'] for cue in sound['cues'])
