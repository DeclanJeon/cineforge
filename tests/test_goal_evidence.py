import hashlib
import json

import pytest

from cineforge import goal_evidence as ge
from cineforge.cli import main
from cineforge.pipeline import Project

G = {'version': 1, 'revision': 1, 'kind': 'text_storyboard', 'request': 'x', 'constraints': {'duration_s': 15.0, 'aspect': '9:16'}}


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}


@pytest.fixture
def board(tmp_path):
    main(['new', '15초 9:16 코미디 숏드라마 스토리보드만', '--projects-dir', str(tmp_path), '--project-id', 'p',
          '--provider', 'mock', '--goal', 'auto'])
    return tmp_path / 'p'


def edit(root, rel, fn):
    d = json.loads((root / rel).read_text())
    fn(d)
    (root / rel).write_text(json.dumps(d))


def test_good_board_satisfied_and_evaluation_is_read_only(board):
    before = snapshot(board)
    assert ge.evaluate(board, G)['satisfied']
    assert snapshot(board) == before


def test_empty_missing_and_broken_boards(board):
    edit(board, 'ssot/scene.json', lambda d: d['data']['cuts'].append(dict(d['data']['cuts'][0])))
    assert 'duplicate_cut_ids' in ge.evaluate(board, G)['unmet']
    edit(board, 'ssot/scene.json', lambda d: d['data'].update(cuts=[]))
    assert ge.evaluate(board, G)['unmet'] == ['storyboard_empty']


def test_camera_reference_break_and_frame_boundary(board):
    edit(board, 'ssot/camera.json', lambda d: d['data']['cuts'].pop())
    assert any(u.startswith('camera_missing') for u in ge.evaluate(board, G)['unmet'])


@pytest.mark.parametrize('want,ok', [(15.04, True), (15.05, False), (14.96, True), (14.9, False)])
def test_one_frame_boundary(board, want, ok):
    g = {**G, 'constraints': {'duration_s': want}}
    assert ge.evaluate(board, g)['satisfied'] is ok


def test_aspect_mismatch(board):
    g = {**G, 'constraints': {'aspect': '16:9'}}
    assert any(u.startswith('aspect_mismatch') for u in ge.evaluate(board, g)['unmet'])


def test_stage_done_without_artifacts_is_not_enough(board):
    (board / 'ssot/scene.json').unlink()
    assert ge.evaluate(board, G)['unmet'] == ['storyboard_missing']
