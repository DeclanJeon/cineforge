import json
import os
import stat

from cineforge.cli import main
from cineforge.mcp_discovery import discover, import_config, matches, provider_of
from cineforge.sound import status


def _home(tmp_path):
    home = tmp_path / 'home'
    (home / '.codex').mkdir(parents=True)
    (home / '.codex/config.toml').write_text("""
[mcp_servers.elevenlabs]
command = "uvx"
args = ["elevenlabs-mcp"]
[mcp_servers.elevenlabs.env]
ELEVENLABS_API_KEY = "sk-secret-value"

[mcp_servers.fish-audio]
command = "fish-audio-mcp"

[mcp_servers.unrelated]
command = "x"
""".strip())
    (home / '.claude.json').write_text(json.dumps({'mcpServers': {
        'suno': {'command': 'suno-mcp', 'args': ['--stdio']},
        'typecast': {'url': 'https://mcp.example/typecast'}}}))
    (home / '.gemini').mkdir()
    (home / '.gemini/settings.json').write_text('{broken json')
    return home


def test_discovers_other_agents_without_copying_secrets(tmp_path):
    home = _home(tmp_path)
    rows = discover(home)
    found = matches(rows)
    assert set(found) == {'elevenlabs', 'fish_audio', 'suno', 'typecast'}
    assert found['elevenlabs']['agent'] == 'codex' and found['elevenlabs']['command'] == 'uvx'
    assert found['suno']['source'].endswith('.claude.json')
    assert found['typecast']['url'].startswith('https://')
    target = import_config(rows, target=tmp_path / 'cineforge' / 'mcp.json')
    text = target.read_text()
    assert 'sk-secret-value' not in text
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    payload = json.loads(text)
    assert payload['providers']['elevenlabs']['env_keys'] == ['ELEVENLABS_API_KEY']
    assert payload['providers']['elevenlabs']['source'].endswith('config.toml')


def test_aliases_and_unknown_names():
    assert provider_of('fish-audio') == 'fish_audio'
    assert provider_of('ElevenLabs') == 'elevenlabs'
    assert provider_of('Ludyte') == 'ludyte'
    assert provider_of('playwright') is None


def test_cli_setup_syncs_automatically_and_updates_on_change(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path)
    monkeypatch.setenv('HOME', str(home))
    assert main(['setup']) == 0
    assert '자동 동기화' in capsys.readouterr().out
    cache = home / '.config/cineforge/mcp.json'
    first = json.loads(cache.read_text())
    assert set(first['providers']) == {'elevenlabs', 'fish_audio', 'suno', 'typecast'}
    (home / '.claude.json').write_text(json.dumps({'mcpServers': {'suno': {'command': 'suno-v2'}}}))
    assert main(['setup']) == 0
    second = json.loads(cache.read_text())
    assert second['providers']['suno']['command'] == 'suno-v2'
    assert 'typecast' not in second['providers']
    capsys.readouterr()
    assert main(['setup', '--discover']) == 0
    out = json.loads(capsys.readouterr().out)
    assert 'elevenlabs' in out['matched'] and out['servers']
    assert main(['setup', '--import-mcp']) == 0
    assert json.loads(capsys.readouterr().out)['providers']


def test_sync_reports_conflicts_and_keeps_first_source(tmp_path):
    from cineforge.mcp_discovery import sync
    rows = [{'agent': 'codex', 'source': '/a/config.toml', 'name': 'suno', 'command': 'a', 'env_keys': []},
            {'agent': 'pi', 'source': '/b/mcp.json', 'name': 'suno', 'command': 'b', 'env_keys': ['SUNO_API_KEY']}]
    report = sync(rows, target=tmp_path / 'mcp.json')
    assert report['conflicts'][0]['provider'] == 'suno'
    assert report['conflicts'][0]['chosen'] == '/b/mcp.json'
    assert report['conflicts'][0]['alternatives'] == ['/a/config.toml']
    payload = json.loads((tmp_path / 'mcp.json').read_text())
    assert payload['providers']['suno']['command'] == 'b'
    assert payload['providers']['suno']['env_keys'] == ['SUNO_API_KEY']


def test_no_sync_leaves_existing_cache(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path)
    monkeypatch.setenv('HOME', str(home))
    cache = home / '.config/cineforge/mcp.json'
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({'providers': {'suno': {'command': 'old'}}}))
    assert main(['setup', '--no-sync']) == 0
    assert json.loads(cache.read_text())['providers']['suno']['command'] == 'old'
