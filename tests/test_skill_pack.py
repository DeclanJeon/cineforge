import json
import shutil
from pathlib import Path

import pytest

from cineforge.cli import main
from cineforge.pipeline import Project
from cineforge.skills import check
from conftest import SAMPLE_REQUEST, make_skill_pack


def create_cli(parent: Path, name: str, *, provider: str = 'mock') -> int:
    return main(['new', SAMPLE_REQUEST, '--projects-dir', str(parent), '--project-id', name,
                 '--provider', provider, '--until', 'S06_storyboard'])


@pytest.mark.parametrize('failure', ['unsupported', 'authority', 'escape', 'missing-stage', 'missing-file', 'drift'])
def test_diagnostics_refuse_bad_packs(tmp_path, failure):
    root = make_skill_pack(tmp_path / 'pack')
    manifest = root / 'manifest.json'
    data = json.loads(manifest.read_bytes())
    contract = data['integrations']['cineforge']
    row = contract['stages']['S06_storyboard']
    if failure == 'unsupported':
        contract['contract_version'] = 2
    if failure == 'authority':
        row['authority_granted'] = True
    if failure == 'escape':
        row['refs'] = ['../private.md']
    if failure == 'missing-stage':
        del contract['stages']['S06_storyboard']
    if failure == 'missing-file':
        (root / 'storyboarding-video/SKILL.md').unlink()
    if failure == 'drift':
        (root / 'storyboarding-video/SKILL.md').write_text('unexpected', encoding='utf-8')
    manifest.write_text(json.dumps(data), encoding='utf-8')
    assert check(root)['status'] == ('incompatible' if failure == 'unsupported' else 'invalid')


def test_switch_pack_only_changes_new_projects(tmp_path, monkeypatch, capsys):
    a = make_skill_pack(tmp_path / 'a', 'alpha')
    b = make_skill_pack(tmp_path / 'b', 'beta')
    manifest = b / 'manifest.json'
    data = json.loads(manifest.read_bytes())
    data['integrations']['cineforge']['stages']['S06_storyboard'].update(owners=['creative-production'], route='R-pinned-beta')
    manifest.write_text(json.dumps(data), encoding='utf-8')

    monkeypatch.setenv('CINEFORGE_SKILL_PACK', str(a))
    assert create_cli(tmp_path, 'first') == 0
    first = Project(tmp_path / 'first')
    old = first.read('handoffs/S06_storyboard.json')
    lock = first.read('skill_pack.lock.json')
    assert lock['version'] == 'alpha'
    assert old['craft_refs'] == ['storyboarding-video/alpha.md']

    monkeypatch.setenv('CINEFORGE_SKILL_PACK', str(b))
    assert create_cli(tmp_path, 'second') == 0
    new = Project(tmp_path / 'second').read('handoffs/S06_storyboard.json')
    assert new['craft_refs'] == ['storyboarding-video/beta.md']
    assert new['owner_skills'] == ['creative-production']
    assert new['owner_entrypoints'] == ['creative-production/SKILL.md']
    assert new['route'] == 'R-pinned-beta' and new['route'] != old['route']
    for key in ['authority_required', 'authority_granted', 'outputs_expected']:
        assert new[key] == old[key]
    capsys.readouterr()
    assert main(['status', str(first.root), '--json']) == 0
    status = json.loads(capsys.readouterr().out)
    assert status['stages']['S06_storyboard']['skills'] == old['owner_skills']
    assert status['skill_pack']['version'] == 'alpha'
    assert main(['run', str(first.root), '--until', 'S07_assets']) == 2
    assert first.read('handoffs/S07_assets.json') is None

    moved = a.rename(tmp_path / 'moved')
    monkeypatch.setenv('CINEFORGE_SKILL_PACK', str(moved))
    assert main(['run', str(first.root), '--until', 'S07_assets']) == 0
    assert first.read('handoffs/S07_assets.json')['skill_pack']['root'] == str(moved)
    assert first.read('skill_pack.lock.json') == lock


def test_explicit_missing_pack_leaves_no_project(tmp_path, monkeypatch):
    monkeypatch.setenv('CINEFORGE_SKILL_PACK', str(tmp_path / 'absent'))
    assert create_cli(tmp_path, 'rejected', provider='host') == 2
    assert not (tmp_path / 'rejected').exists()


def test_copied_layout_reads_support_inventory(tmp_path):
    source = make_skill_pack(tmp_path / 'source')
    target = tmp_path / 'installed'
    shutil.copytree(source, target)
    support = target / 'video-production-assets/support'
    support.mkdir(parents=True)
    (target / 'manifest.json').rename(support / 'manifest.json')
    (target / 'integrations').rename(support / 'integrations')
    assert check(target)['status'] == 'ready'


def test_published_schema_covers_engine_stage_ids():
    from cineforge.schemas import load_schema
    from cineforge.skill_pack_manifest import STAGES

    shape = load_schema('skill_pack')['properties']['stages']
    assert set(shape['required']) == set(shape['propertyNames']['enum']) == STAGES


def test_duplicate_installs_are_distinguished_from_conflicting_versions(tmp_path, monkeypatch):
    from cineforge import skills

    a = make_skill_pack(tmp_path / 'a', 'alpha')
    copy = tmp_path / 'copy'
    shutil.copytree(a, copy)
    b = make_skill_pack(tmp_path / 'b', 'beta')
    monkeypatch.delenv('CINEFORGE_SKILL_PACK')
    monkeypatch.setattr(skills, 'DEFAULT_ROOTS', (a, copy))
    assert check()['status'] == 'ready'
    monkeypatch.setattr(skills, 'DEFAULT_ROOTS', (a, copy, b))
    assert check()['status'] == 'ambiguous'
    assert check(b)['version'] == 'beta'


def test_outside_pack_link_and_uninventoried_file_are_rejected(tmp_path):
    root = make_skill_pack(tmp_path / 'pack')
    owned = root / 'storyboarding-video'
    injected = owned / 'helper.py'
    injected.write_text('not part of the release', encoding='utf-8')
    assert check(root)['status'] == 'invalid'
    injected.unlink()
    outside = tmp_path / 'outside'
    (owned / 'SKILL.md').rename(outside)
    (owned / 'SKILL.md').symlink_to(outside)
    assert check(root)['status'] == 'invalid'


def test_mock_without_pack_remains_structure_only(tmp_path, monkeypatch, capsys):
    from cineforge import skills

    monkeypatch.delenv('CINEFORGE_SKILL_PACK')
    monkeypatch.setattr(skills, 'DEFAULT_ROOTS', ())
    assert main(['new', SAMPLE_REQUEST, '--projects-dir', str(tmp_path), '--project-id', 'mock',
                 '--provider', 'mock', '--image-limit', '100']) == 0
    project = Project(tmp_path / 'mock')
    assert project.read('plan.json')
    assert project.read('handoffs/S08_generation.json') is None
    assert project.progress()['stages']['S08_generation']['status'] == 'blocked'
    assert not (project.root / 'assets/image_jobs').exists()
    capsys.readouterr()
    assert main(['status', str(project.root), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['skill_pack'] == {'mode': 'mock/unbound'}


def test_deleted_lock_cannot_be_treated_as_legacy(tmp_path):
    assert create_cli(tmp_path, 'p') == 0
    root = tmp_path / 'p'
    (root / 'skill_pack.lock.json').unlink()
    assert main(['run', str(root)]) == 2
    assert not (root / 'handoffs/S07_assets.json').exists()


def test_legacy_project_does_not_use_installed_pack(tmp_path, monkeypatch, capsys):
    from cineforge import skills

    assert create_cli(tmp_path, 'p') == 0
    root = tmp_path / 'p'
    project = Project(root)
    old_style = {key: value for key, value in project.meta.items() if not key.startswith('skill_pack_')}
    project.write('project.json', old_style)
    (root / 'skill_pack.lock.json').unlink()
    monkeypatch.delenv('CINEFORGE_SKILL_PACK')
    monkeypatch.setattr(skills, 'DEFAULT_ROOTS', ())
    assert main(['run', str(root), '--until', 'S07_assets']) == 0
    assert 'skill_pack' not in project.read('handoffs/S07_assets.json')
    capsys.readouterr()
    assert main(['status', str(root), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['skill_pack'] == {'mode': 'legacy/unpinned'}


def test_waiting_handoff_relocates_without_resealing_evidence(tmp_path, monkeypatch):
    pack = make_skill_pack(tmp_path / 'pack')
    monkeypatch.setenv('CINEFORGE_SKILL_PACK', str(pack))
    assert create_cli(tmp_path, 'p') == 0
    project = Project(tmp_path / 'p')
    project.grant(execution=True)
    stage = 'S08_generation'
    project.run()
    assert project.progress()['stages'][stage]['status'] == 'waiting_external'
    path = f'handoffs/{stage}.json'
    original = project.read(path)

    moved = pack.rename(tmp_path / 'moved')
    monkeypatch.setenv('CINEFORGE_SKILL_PACK', str(moved))
    project.run()
    relocated = project.read(path)
    assert relocated == {**original, 'skill_pack': {**original['skill_pack'], 'root': str(moved)}}


def test_pack_drift_stops_all_production_entrypoints(tmp_path, monkeypatch):
    from cineforge import assembly, delivery, image_queue, jobs, local_motion
    from cineforge.skill_pack_manifest import SkillPackError

    pack = make_skill_pack(tmp_path / 'pack')
    monkeypatch.setenv('CINEFORGE_SKILL_PACK', str(pack))
    assert create_cli(tmp_path, 'p') == 0
    project = Project(tmp_path / 'p')
    (pack / 'storyboarding-video/SKILL.md').write_text('drift', encoding='utf-8')
    root = project.root
    operations = [
        lambda: project.complete('S08_generation', ['take.mp4']),
        lambda: jobs.write_envelope(root, 'S08_audio', ()),
        lambda: jobs.record_results(root, 'S08_audio', []),
        lambda: local_motion.render(root, tmp_path / 'font.ttf'),
        lambda: local_motion.deliver(root, '0' * 64),
        lambda: delivery.deliver(root),
        lambda: assembly.render(root, {}),
        lambda: image_queue.generate(root, [], 0),
    ]
    for operation in operations:
        with pytest.raises(SkillPackError, match='inventory hash mismatch'):
            operation()
    assert not (root / 'final').exists() and not (root / 'jobs').exists()


def test_pointer_precedes_default_roots(tmp_path, monkeypatch):
    from cineforge import skill_store, skills

    a = make_skill_pack(tmp_path / 'a', 'alpha')
    b = make_skill_pack(tmp_path / 'b', 'beta')
    monkeypatch.delenv('CINEFORGE_SKILL_PACK')
    monkeypatch.setattr(skills, 'DEFAULT_ROOTS', (b,))
    assert check()['version'] == 'beta'
    skill_store.write_pointer('alpha', a)
    assert check()['version'] == 'alpha'
    monkeypatch.setenv('CINEFORGE_SKILL_PACK', str(b))
    assert check()['version'] == 'beta'


def test_pinned_project_finds_old_version(tmp_path, monkeypatch):
    from cineforge import skill_store, skills
    from cineforge.skill_pack_manifest import read_manifest

    old = make_skill_pack(skill_store.pack_dir('2.63'), '2.63')
    new = make_skill_pack(skill_store.pack_dir('2.64'), '2.64')
    monkeypatch.delenv('CINEFORGE_SKILL_PACK')
    monkeypatch.setattr(skills, 'DEFAULT_ROOTS', ())
    skill_store.write_pointer('2.64', new)
    assert skills.discover().root == new.resolve()
    pinned = read_manifest(old, 'manifest.json')
    assert skills.discover(expected=pinned).root == old.resolve()
