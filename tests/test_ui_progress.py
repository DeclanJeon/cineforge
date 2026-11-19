import json
import re
from pathlib import Path

from cineforge.cli import main
from cineforge.progress import share, snapshot
from cineforge.ui import ANSI, banner, colorize, logo, panel, supports_color
from conftest import SAMPLE_REQUEST


def _project(tmp_path):
    main(['new', SAMPLE_REQUEST, '--projects-dir', str(tmp_path), '--project-id', 'p', '--provider', 'mock',
          '--no-nonstop', '--until', 'S03_plan'])
    return tmp_path / 'p'


def test_logo_and_banner_are_plain_when_color_is_off():
    art = logo()
    assert 'CINEFORGE' in art and art.count('\n') >= 2
    assert '\x1b' not in art and '\x1b' not in banner('0.1.0')
    assert '0.1.0' in banner('0.1.0')


def test_colorize_respects_no_color_and_non_tty(monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    assert colorize('x', 'accent', color=True) == f'{ANSI["accent"]}x{ANSI["reset"]}'
    assert colorize('x', 'accent', color=False) == 'x'
    monkeypatch.setenv('NO_COLOR', '1')
    assert supports_color(stream=None) is False


def test_panel_shows_rates_blockers_and_next_action(tmp_path, capsys):
    root = _project(tmp_path)
    capsys.readouterr()
    text = panel(json.loads((root / 'progress.json').read_text()), color=False)
    assert '진행률' in text and '%' in text and '작업률' in text
    assert 'G1' in text and 'S08' in text
    assert '다음' in text and 'G1' in text.split('다음')[1].split('\n')[0]
    assert '\x1b' not in text
    assert capsys.readouterr().out == ''


def test_snapshot_is_stable_for_agents_and_written_atomically(tmp_path):
    root = _project(tmp_path)
    state = snapshot(root)
    assert state['schema_version'] == 1
    assert state['project_id'] == 'p'
    assert set(state) >= {'current_stage', 'progress_rate', 'task_rate', 'stages', 'next_action', 'blocked'}
    stage = next(iter(state['stages'].values()))
    assert set(stage) == {'status', 'done', 'total', 'qa', 'note', 'skills'}
    path = share(root)
    assert path == root / 'agent_io' / 'progress.json'
    assert json.loads(path.read_text()) == state
    assert not path.with_suffix('.tmp').exists()


def test_status_json_carries_the_shared_snapshot(tmp_path, capsys):
    root = _project(tmp_path)
    capsys.readouterr()
    assert main(['status', str(root), '--json']) == 0
    out = json.loads(capsys.readouterr().out)
    assert out['schema_version'] == 1 and out['project_id'] == 'p'
    assert '\x1b' not in json.dumps(out)


def test_human_status_prints_banner_and_panel(tmp_path, capsys, monkeypatch):
    pid = _project(tmp_path)
    capsys.readouterr()
    monkeypatch.setenv('NO_COLOR', '1')
    assert main(['status', str(pid)]) == 0
    out = capsys.readouterr().out
    assert 'CINEFORGE' in out and '진행률' in out
    assert not re.search(r'\x1b\[', out)
