import json
import shutil
import subprocess
from unittest import mock

import pytest

from closure_fixture import prepared
from cineforge import goal_attempts, goal_contract
from cineforge.cli import main
from cineforge.pipeline import Project
from cineforge.video_jobs import select_take

FFMPEG = shutil.which('ffmpeg')
REQ = '15초 9:16 코미디 숏드라마를 최종 MP4로 납품해줘'
pytestmark = pytest.mark.skipif(FFMPEG is None, reason='ffmpeg required')


@pytest.fixture(autouse=True)
def _no_real_generation(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('real image generation attempted')
    monkeypatch.setattr('cineforge.image_queue.generate', boom)


def new_project(tmp_path):
    p = prepared(tmp_path, '15초 코미디 숏드라마, 시네마틱 실사')
    goal = goal_contract.resolve(REQ)['goal']
    goal_contract.write(p.root, goal)
    return p


def drive(root, capsys):
    capsys.readouterr()
    code = main(['goal', 'drive', str(root), '--json'])
    return code, json.loads(capsys.readouterr().out[capsys.readouterr().out.find('{'):] or '{}') if False else None


def state(root, capsys):
    capsys.readouterr()
    code = main(['goal', 'drive', str(root), '--json'])
    out = capsys.readouterr().out
    return code, json.loads(out[out.index('{'):])


def host_supplies_media(p, tmp_path):
    from cineforge.audio_jobs import apply_results, plan_jobs
    p.write('edit/proxy.json', {'width': 180, 'height': 320})
    wav = p.root / 'audio/tone.wav'
    wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=300:duration=1', '-af', 'volume=-10dB', '-ac', '2', '-ar', '48000', '-y', str(wav)], check=True)
    apply_results(p.root, [{'job_id': j.job_id, 'status': 'accepted', 'path': 'audio/tone.wav'} for j in plan_jobs(p.root)])
    for cut in p.read('ssot/scene.json')['data']['cuts']:
        clip = p.root / 'takes' / f'{cut["cut_id"]}.mp4'
        clip.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=navy:s=192x108:r=24:d={float(cut["duration"]) + 0.2}',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(clip)], check=True)
        select_take(p.root, cut['cut_id'], f'takes/{cut["cut_id"]}.mp4')


def test_authority_then_single_host_request(tmp_path, capsys):
    p = new_project(tmp_path)
    code, r = state(p.root, capsys)
    assert (code, r['state']) == (3, 'needs_user') and 'execution' in r['next_action']
    p.grant(execution=True)
    code, first = state(p.root, capsys)
    assert (code, first['state']) == (3, 'waiting_external') and first['request_id']
    with mock.patch.object(Project, 'run') as run:
        code, second = state(p.root, capsys)
    run.assert_not_called()
    assert second['request_id'] == first['request_id'] and code == 3


def test_request_to_delivery_with_user_gates(tmp_path, capsys, monkeypatch):
    p = new_project(tmp_path)
    p.grant(execution=True, edit=True)
    host_supplies_media(p, tmp_path)
    code, r = state(p.root, capsys)
    assert (code, r['state']) == (3, 'needs_user'), r
    assert 'verify' in r['next_action']
    assert not (p.root / 'final/delivery.json').exists()
    monkeypatch.setattr('sys.stdin.isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda prompt='': 'VERIFY')
    assert main(['verify', str(p.root), '--all', '--attest', '파일 확인']) == 0
    code, r = state(p.root, capsys)
    assert r['reason'] == 'user_approval_missing' and code == 3
    assert main(['deliver', str(p.root)]) == 1          # manual deliver refused without approval for this render
    assert main(['accept', str(p.root), 'final']) == 0
    code, r = state(p.root, capsys)
    assert (code, r['state']) == (0, 'satisfied'), r
    saved = p.read('skill_pack.lock.json')
    delivered = p.read('final/delivery.json')['skill_pack']
    for field in ('name', 'version', 'contract_version', 'manifest_sha256', 'inventory_sha256'):
        assert delivered[field] == saved[field]
    assert delivered['verified_usage'] == 'unconfirmed'
    # a replaced render invalidates delivery evidence and approval
    (p.root / 'edit/render.mp4').write_bytes((p.root / 'edit/render.mp4').read_bytes() + b'x')
    code, r = state(p.root, capsys)
    assert code != 0 and 'render_differs_from_final' in r['unmet']


def test_goal_drive_wrong_pack_does_not_create_an_attempt(tmp_path, monkeypatch, capsys):
    from conftest import make_skill_pack

    project = new_project(tmp_path)
    project.grant(execution=True)
    project.run(until='G2_preproduction_review')
    assert project.progress()['stages']['G2_preproduction_review']['status'] == 'done'
    b = make_skill_pack(tmp_path / 'different-pack', 'other')
    monkeypatch.setenv('CINEFORGE_SKILL_PACK', str(b))
    capsys.readouterr()
    assert main(['goal', 'drive', str(project.root), '--json']) == 2
    assert 'restore and select' in capsys.readouterr().err
    assert not (project.root / 'goal/attempts').exists()


def test_concurrent_drive_is_busy(tmp_path, capsys):
    p = new_project(tmp_path)
    with goal_attempts.project_lock(p.root):
        code, r = state(p.root, capsys)
    assert (code, r['state']) == (3, 'busy')


def test_crash_between_intent_and_issue_needs_reconciliation(tmp_path, capsys):
    p = new_project(tmp_path)
    goal = goal_contract.read(p.root)
    key = goal_attempts.attempt_key(goal, 'handoff:S08_generation', goal_attempts.input_hash(p.root))
    goal_attempts.begin(p.root, key, 'handoff:S08_generation', external=True, inputs=goal_attempts.input_hash(p.root), revision=goal['revision'])
    code, r = state(p.root, capsys)
    assert (code, r['state']) == (4, 'needs_reconciliation')
    assert main(['goal', 'reconcile', str(p.root), key, '--issued']) == 0
    code, r = state(p.root, capsys)
    assert r['state'] == 'waiting_external' and r['request_id'] == key


def test_goal_revision_change_requires_new_attempt(tmp_path):
    g = goal_contract.resolve(REQ)['goal']
    assert goal_attempts.attempt_key(g, 'a', 'h') != goal_attempts.attempt_key({**g, 'revision': 2}, 'a', 'h')
