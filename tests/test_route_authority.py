import json
import time

import pytest

from cineforge.cli import main
from cineforge.jobs import JobError, require_authorized
from cineforge.route import evaluate, judge
from closure_fixture import prepared
from cineforge.audio_jobs import plan_jobs


def test_route_meets_threshold_on_dev_and_holdout(tmp_path, capsys):
    dev = evaluate()
    assert dev['total'] >= 25 and dev['accuracy'] >= 0.9
    assert main(['route', '--eval']) == 0
    assert json.loads(capsys.readouterr().out)['accuracy'] >= 0.9
    assert main(['route', '--holdout']) == 0
    assert json.loads(capsys.readouterr().out)['accuracy'] >= 0.9


def test_route_boundaries():
    assert judge('90초 드라마 만들어줘')['route'] == 'cineforge'
    assert judge('영상이 안 돼요 재생이 안 됨')['route'] == 'other'
    assert judge('이미지 한 장 생성해줘')['route'] == 'other'
    assert judge('영상 만들 때 주의할 점 설명해줘')['route'] == 'other'
    assert judge('')['route'] == 'other'


def test_execution_approval_expires(tmp_path):
    project = prepared(tmp_path)
    project.grant(execution=True, providers=['suno'], execution_until=int(time.time()) - 1)
    with pytest.raises(JobError, match='execution_expired'):
        require_authorized(project.root, plan_jobs(project.root))


def test_authorize_requires_a_terminal(tmp_path, capsys, monkeypatch):
    project = prepared(tmp_path)
    capsys.readouterr()
    monkeypatch.setattr('sys.stdin.isatty', lambda: False)
    assert main(['authorize', str(project.root), '--hours', '1']) == 1
    monkeypatch.setattr('sys.stdin.isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda prompt='': 'no')
    assert main(['authorize', str(project.root)]) == 1
    monkeypatch.setattr('builtins.input', lambda prompt='': 'APPROVE')
    assert main(['authorize', str(project.root), '--spend-ceiling', '20USD', '--providers', 'suno', '--hours', '2']) == 0
    auth = json.loads((project.root / 'authority.json').read_text())
    assert auth['execution'] is True and auth['spend_ceiling'] == '20USD'
    assert auth['providers'] == ['suno'] and auth['execution_until'] > time.time()
