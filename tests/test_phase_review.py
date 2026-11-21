import json
from pathlib import Path

import pytest

from cineforge.phase_review import PRE, review


def setup(root):
    (root/'project.json').write_text('{"provider_mode":"host"}')
    for name in PRE:
        path = root/name
        path.parent.mkdir(exist_ok=True)
        path.write_text('fixture')
    (root/'ssot/scene.json').write_text('{"data":{"cuts":[{"cut_id":"C2"},{"cut_id":"C3"}]}}')


def respond(root, issues):
    requests = sorted((root/'agent_io/requests').glob('*.json'), key=lambda p: p.stat().st_mtime_ns)
    packet = json.loads(requests[-1].read_text())
    Path(packet['response_path']).write_text(json.dumps({'evidence': 'inspection fixture', 'cut_evidence': {'C2':'reaction timing', 'C3':'prop reveal'}, 'findings': issues}))


def test_wait_and_first_pass_success(tmp_path):
    setup(tmp_path)
    for _ in range(2):
        with pytest.raises(ValueError, match='pending'):
            review(tmp_path, 'pre')
    assert not (tmp_path/'reviews/pre-passes.json').exists()
    respond(tmp_path, [])
    review(tmp_path, 'pre')
    review(tmp_path, 'pre')
    assert len(json.loads((tmp_path/'reviews/pre-passes.json').read_text())) == 1


def test_consolidated_fixes_two_passes_then_skip(tmp_path):
    setup(tmp_path)
    with pytest.raises(ValueError, match='pending'):
        review(tmp_path, 'prompt', ['v1'])
    respond(tmp_path, ['C2 reacts before cue', 'C3 shows inside key too early'])
    for _ in range(2):
        with pytest.raises(ValueError, match='apply consolidated'):
            review(tmp_path, 'prompt', ['v1'])
    with pytest.raises(ValueError, match='pending'):
        review(tmp_path, 'prompt', ['v2'])
    respond(tmp_path, ['minor residual risk'])
    for _ in range(3):
        review(tmp_path, 'prompt', ['v2'])
    assert len(list((tmp_path/'agent_io/requests').glob('*.json'))) == 2
