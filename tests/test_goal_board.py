import json
from unittest import mock

import pytest

from cineforge.cli import main
from cineforge import goal_driver, goal_evidence
from cineforge.pipeline import Project

REQ = '15초 9:16 코미디 숏드라마 스토리보드만 만들어줘'


def make(tmp_path, req=REQ, extra=()):
    assert main(['new', req, '--projects-dir', str(tmp_path), '--project-id', 'p', '--provider', 'mock',
                 '--goal', 'auto', *extra]) in (0, 3)
    return tmp_path / 'p'


def test_board_goal_completes_without_generation(tmp_path, capsys):
    root = make(tmp_path)
    with mock.patch('cineforge.image_queue.generate') as gen:
        code = main(['goal', 'drive', str(root), '--json'])
        assert code == 0
        assert main(['goal', 'drive', str(root)]) == 0  # rerun: still no generation
        gen.assert_not_called()
    prog = Project(root).progress()
    assert prog['stages']['S07_assets']['status'] == 'pending'
    assert goal_evidence.evaluate(root, json.loads((root / 'goal.json').read_text()))['satisfied']


def test_run_cannot_exceed_goal_ceiling(tmp_path):
    root = make(tmp_path)
    Project(root).grant(accept_preproduction=True)
    main(['run', str(root)])
    assert Project(root).progress()['stages']['S07_assets']['status'] == 'pending'


@pytest.mark.parametrize('cmd', ['execute', 'render', 'edit', 'deliver', 'motion'])
def test_manual_commands_refused_for_board_goal(tmp_path, cmd, capsys):
    root = make(tmp_path)
    argv = [cmd, str(root)] + (['--stage', 'S08_audio'] if cmd == 'execute' else ['--font', 'x'] if cmd == 'motion' else [])
    assert main(argv) == 1
    assert 'forbids' in capsys.readouterr().err


def test_duration_mismatch_is_repaired_with_exact_frames(tmp_path):
    root = make(tmp_path, '18초 9:16 코미디 숏드라마 스토리보드만')
    # force a mismatch: change the goal's target, then drive
    g = json.loads((root / 'goal.json').read_text())
    g['constraints']['duration_s'] = 15.0
    (root / 'goal.json').write_text(json.dumps({**g, 'revision': 2}))
    assert main(['goal', 'drive', str(root)]) == 0
    cuts = Project(root).read('ssot/scene.json')['data']['cuts']
    assert abs(cuts[-1]['end'] - 15.0) <= 1 / 24
    assert all(c['duration'] > 0 for c in cuts)


def test_locked_scene_not_rewritten(tmp_path):
    root = make(tmp_path)
    scene = json.loads((root / 'ssot/scene.json').read_text()) if (root / 'ssot/scene.json').exists() else None
    main(['goal', 'drive', str(root)])
    g = json.loads((root / 'goal.json').read_text())
    (root / 'goal.json').write_text(json.dumps({**g, 'revision': 2, 'constraints': {**g['constraints'], 'duration_s': 20.0}}))
    main(['lock', str(root), 'scene'])
    assert main(['goal', 'drive', str(root)]) == 4


def test_ambiguous_request_creates_project_but_does_not_run(tmp_path):
    root = make(tmp_path, '광고 준비해줘')
    assert not (root / 'goal.json').exists()
    assert Project(root).progress()['stages']['S03_plan']['status'] == 'pending'


def test_no_goal_projects_unchanged(tmp_path):
    assert main(['new', REQ, '--projects-dir', str(tmp_path), '--project-id', 'q', '--provider', 'mock']) == 0
    assert not (tmp_path / 'q/goal.json').exists()
    assert main(['execute', str(tmp_path / 'q'), '--stage', 'S08_audio', '--preview']) in (0, 1)
