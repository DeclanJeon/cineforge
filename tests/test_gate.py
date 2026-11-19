import json
from pathlib import Path

from cineforge.cli import main
from cineforge.gate import check, promote
from cineforge.jobs import binding
from cineforge.pipeline import Project
from conftest import SAMPLE_REQUEST


def _project(tmp_path):
    main(['new', SAMPLE_REQUEST, '--projects-dir', str(tmp_path), '--project-id', 'p', '--provider', 'mock',
          '--no-nonstop', '--until', 'S03_plan'])
    project = Project(tmp_path / 'p')
    project.grant(accept_plan=True, accept_preproduction=True)
    project.run(until='S07_assets')
    return project


def _make_assets(project, status='available'):
    rows = project.read('assets/asset_registry.json')
    for row in rows['assets']:
        path = project.root / 'assets/generated' / (row['asset_id'] + '.png')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'\x89PNG\r\n\x1a\n' + row['asset_id'].encode())
        row.update(status=status, path=f'assets/generated/{row["asset_id"]}.png', version=1)
    project.write('assets/asset_registry.json', rows, 'asset_registry')
    return rows


def test_gate_blocks_available_assets_until_verified(tmp_path):
    project = _project(tmp_path)
    rows = _make_assets(project)
    report = check(project.root)
    assert report.status == 'fail'
    assert len(report.blockers) == len(rows['assets'])
    assert all('not_verified' in row['reason'] for row in report.blockers)
    assert promote(project.root, [row['asset_id'] for row in rows['assets']], attestation='파일 확인') == len(rows['assets'])
    assert check(project.root).status == 'pass'


def test_gate_detects_changed_or_missing_files(tmp_path):
    project = _project(tmp_path)
    rows = _make_assets(project)
    ids = [row['asset_id'] for row in rows['assets']]
    promote(project.root, ids, attestation='파일 확인')
    target = project.root / rows['assets'][0]['path']
    target.write_bytes(b'\x89PNG\r\n\x1a\nchanged')
    report = check(project.root)
    assert report.status == 'fail' and report.blockers[0]['reason'].startswith('hash_mismatch')
    target.unlink()
    report = check(project.root)
    assert any(row['reason'] == 'file_missing' for row in report.blockers)


def test_promote_refuses_unhashed_or_missing_files(tmp_path):
    project = _project(tmp_path)
    rows = project.read('assets/asset_registry.json')
    project.write('assets/asset_registry.json', rows, 'asset_registry')
    assert promote(project.root, [rows['assets'][0]['asset_id']], attestation='확인') == 0
    assert check(project.root).status == 'fail'


def test_gate_cli_exit_codes_and_json(tmp_path, capsys, monkeypatch):
    project = _project(tmp_path)
    rows = _make_assets(project)
    capsys.readouterr()
    assert main(['gate', str(project.root), '--json']) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'fail' and payload['blockers']
    monkeypatch.setattr('sys.stdin.isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda prompt='': 'VERIFY')
    assert main(['verify', str(project.root), '--asset', rows['assets'][0]['asset_id'], '--attest', '파일 확인']) == 0
    assert main(['gate', str(project.root)]) == 1
    assert main(['verify', str(project.root), '--all', '--attest', '전체 확인']) == 0
    assert main(['gate', str(project.root)]) == 0
    capsys.readouterr()


def test_binding_ignores_project_timestamps(tmp_path):
    project = _project(tmp_path)
    first = binding(project.root)
    progress = json.loads((project.root / 'progress.json').read_text())
    progress['updated_at'] = '2000-01-01T00:00:00Z'
    (project.root / 'progress.json').write_text(json.dumps(progress))
    assert binding(project.root) == first
