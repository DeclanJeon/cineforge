import json
import os
import time
from pathlib import Path

from cineforge import mcp_sync


def _home(tmp_path):
    home = tmp_path / 'home'
    (home / '.codex').mkdir(parents=True)
    (home / '.codex/config.toml').write_text('[mcp_servers.elevenlabs]\ncommand = "uvx"\n')
    (home / '.claude.json').write_text(json.dumps({'mcpServers': {'suno': {'command': 'suno-a'}}}))
    return home


def _wait(predicate, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_background_sync_updates_cache_and_stops(tmp_path, monkeypatch):
    home = _home(tmp_path)
    monkeypatch.setenv('HOME', str(home))
    cache = home / '.config/cineforge/mcp.json'
    started = mcp_sync.start(interval=0.15)
    try:
        assert started['status'] == 'started'
        assert _wait(lambda: cache.is_file()), 'cache not created'
        first = json.loads(cache.read_text())
        assert {'elevenlabs', 'suno'} <= set(first['providers'])
        assert mcp_sync.start()['status'] == 'already_running'
        (home / '.claude.json').write_text(json.dumps({'mcpServers': {'suno': {'command': 'suno-b'}}}))
        assert _wait(lambda: json.loads(cache.read_text())['providers']['suno']['command'] == 'suno-b'), 'cache not refreshed'
        status = mcp_sync.status()
        assert status['running'] is True and status['pid'] == started['pid']
    finally:
        stopped = mcp_sync.stop()
    assert stopped['status'] == 'stopped'
    assert mcp_sync.status()['running'] is False
    assert not (home / '.config/cineforge/mcp-sync.json').exists()
    log = (home / '.config/cineforge/mcp-sync.log').read_text()
    assert 'started' in log and 'synced' in log and 'stopped' in log


def test_stale_pid_state_is_ignored(tmp_path, monkeypatch):
    home = _home(tmp_path)
    monkeypatch.setenv('HOME', str(home))
    state = home / '.config/cineforge/mcp-sync.json'
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({'pid': 999999, 'interval': 5}))
    assert mcp_sync.status()['running'] is False
    assert mcp_sync.stop()['status'] == 'not_running'


def test_cli_actions(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path)
    monkeypatch.setenv('HOME', str(home))
    from cineforge.cli import main
    assert main(['mcp-sync', 'status']) == 0
    assert json.loads(capsys.readouterr().out)['running'] is False
