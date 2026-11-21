import json

import pytest

from cineforge.cli import main
from cineforge.jobs import Job, JobError, write_envelope
from closure_fixture import prepared


def propose(project, tmp_path, capsys):
    path = tmp_path / 'scope.json'
    path.write_text(json.dumps({'lanes': [
        {'kind': 'video_cut', 'provider': 'ludyte', 'model': 'h3', 'max_jobs': 1},
        {'kind': 'bgm', 'provider': 'suno', 'model': 'v6', 'max_jobs': 1,
         'unit': 'credits', 'estimate': '10', 'ceiling': '12'},
    ]}))
    capsys.readouterr()
    assert main(['execution-plan', str(project.root), '--file', str(path)]) == 0
    return json.loads(capsys.readouterr().out)['plan_hash']


def test_noninteractive_approval_binds_jobs_and_paid_quote(tmp_path, capsys, monkeypatch):
    project = prepared(tmp_path)
    monkeypatch.setattr('sys.stdin.isatty', lambda: False)
    digest = propose(project, tmp_path, capsys)
    cli = ['authorize', str(project.root), '--approve-plan']
    video = Job('v1', 'video_cut', 'ludyte', 'send_message', (), 'test', (('model', 'h3'),))
    bgm = Job('a1', 'bgm', 'suno', 'generate', (), 'test', (('model', 'v6'),))
    with pytest.raises(JobError, match='execution_plan_not_approved'):
        write_envelope(project.root, 'S08_video', (video,))
    assert main(cli + ['0' * 64]) == 1
    assert main(cli + [digest]) == 0
    assert not project.authority()['execution']
    with pytest.raises(JobError, match='execution_scope_changed'):
        write_envelope(project.root, 'S08_video', (video, Job('v2', 'video_cut', 'ludyte', 'send_message', (), 'test', video.params)))
    with pytest.raises(JobError, match='execution_scope_changed'):
        write_envelope(project.root, 'S08_video', (Job('v1', 'video_cut', 'ludyte', 'send_message', (), 'test', (('model', 'other'),)),))
    assert write_envelope(project.root, 'S08_video', (video,)).is_file()
    with pytest.raises(JobError, match='execution_quote_required'):
        write_envelope(project.root, 'S08_audio', (bgm,))
    quote = {'a1': {'unit': 'credits', 'amount': '13', 'evidence': 'provider quote'}}
    with pytest.raises(JobError, match='execution_ceiling_exceeded'):
        write_envelope(project.root, 'S08_audio', (bgm,), quotes=quote)
    quote['a1']['amount'] = '11'
    envelope = write_envelope(project.root, 'S08_audio', (bgm,), quotes=quote)
    assert json.loads(envelope.read_text())['authority']['execution_plan_hash'] == digest
    assert main(cli + [digest]) == 0
    assert write_envelope(project.root, 'S08_audio', (bgm,), quotes=quote) == envelope
    quote['a1']['amount'] = '12'
    with pytest.raises(JobError, match='execution_envelope_already_issued'):
        write_envelope(project.root, 'S08_audio', (bgm,), quotes=quote)


def test_revised_scope_needs_new_approval_and_preview_does_not_issue(tmp_path, capsys):
    project = prepared(tmp_path)
    digest = propose(project, tmp_path, capsys)
    assert main(['authorize', str(project.root), '--approve-plan', digest]) == 0
    path = tmp_path / 'scope.json'
    scope = json.loads(path.read_text())
    scope['lanes'][1]['model'] = 'v6-mini'
    path.write_text(json.dumps(scope))
    assert main(['execution-plan', str(project.root), '--file', str(path)]) == 0
    capsys.readouterr()
    assert main(['execute', str(project.root), '--stage', 'S08_audio', '--preview']) == 0
    preview = json.loads(capsys.readouterr().out)
    assert next(dict(row['params'])['model'] for row in preview['jobs'] if row['kind'] == 'bgm') == 'v6-mini'
    assert not (project.root / 'jobs').exists()
    assert main(['execute', str(project.root), '--stage', 'S08_audio']) == 1
    assert 'execution_plan_not_approved' in capsys.readouterr().err
