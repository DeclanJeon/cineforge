import json

from cineforge.assets import image_prompts, registry
from cineforge.cli import main
from cineforge.pipeline import Project
from conftest import SAMPLE_REQUEST


def _project(tmp_path):
    main(['new', SAMPLE_REQUEST, '--projects-dir', str(tmp_path), '--project-id', 'p', '--provider', 'mock',
          '--no-nonstop', '--until', 'S03_plan'])
    project = Project(tmp_path/'p')
    project.grant(accept_plan=True, accept_preproduction=True)
    project.run(until='S07_assets')
    return project


def test_every_planned_asset_has_one_ready_prompt(tmp_path):
    project = _project(tmp_path)
    ssots = {kind: {'version': project.read(f'ssot/{kind}.json')['version'],
                    'data': project.read(f'ssot/{kind}.json')['data']}
             for kind in ('character', 'world', 'scene', 'camera', 'concept')}
    planned = registry('p', ssots)['assets']
    prompts = {row['prompt_id']: row for row in image_prompts('p', ssots, '9:16', 'cinematic')['prompts']}
    for asset in planned:
        row = prompts[asset['asset_id']]
        assert row['kind'] == {'character_master': 'character_sheet', 'wardrobe': 'wardrobe',
                               'location_plate': 'location_spatial_sheet', 'prop': 'prop_reference'}[asset['kind']]
    assert len(prompts) == len(planned) + 2 * len(ssots['scene']['data']['cuts'])
    wardrobe = [r for r in prompts.values() if r['kind'] == 'wardrobe']
    assert wardrobe and all(any(ref.endswith('-MASTER') for ref in row['refs']) for row in wardrobe)
    for row in prompts.values():
        if row['kind'] in ('character_sheet', 'location_spatial_sheet'):
            assert len(row['view_ids']) == (7 if row['kind'] == 'character_sheet' else 4)
    for cut in ssots['scene']['data']['cuts']:
        start = prompts[f"IMG-{cut['cut_id']}-S"]
        assert set(start['refs']) == {f"A-{cid}-MASTER" for cid in cut['characters']} | {f"A-{cut['location_id']}"} | {f"A-{w}" for w in cut['start_state']['wardrobe'].values()}


def test_generated_assets_become_available(tmp_path, monkeypatch):
    import base64
    import cineforge.image_queue as iq
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlGAAAAAASUVORK5CYII=')
    seen = []

    def local(row, refs, output, *, supervisor_fd):
        seen.append(row['prompt_id'])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(png)

    monkeypatch.setattr(iq, 'codex_imagen', local)
    main(['new', SAMPLE_REQUEST, '--projects-dir', str(tmp_path), '--project-id', 'q', '--provider', 'mock',
          '--image-limit', '100'])
    project = Project(tmp_path/'q')
    registry_rows = project.read('assets/asset_registry.json')['assets']
    assert registry_rows and all(row['status'] == 'available' for row in registry_rows)
    assert all(row['path'] and row['sha256'] for row in registry_rows)
    assert {row['asset_id'] for row in registry_rows} <= set(seen)
    project.run()
    assert sorted(seen) == sorted(set(seen))


def test_sound_design_exists_before_storyboard(tmp_path):
    project = _project(tmp_path)
    script = (project.root / 'script.md').read_text(encoding='utf-8')
    assert '사운드' in script and ('OST' in script or 'BGM' in script)
    scene = project.read('ssot/scene.json')['data']['cuts']
    assert all('sound' in cut for cut in scene)
    audio = project.read('ssot/audio.json')['data']
    kinds = {cue['type'] for cue in audio['cues']}
    assert {'OST', 'BGM', 'AMBIENCE'} <= kinds
    ost = [cue for cue in audio['cues'] if cue['type'] == 'OST']
    assert len(ost) >= 2 and ost[0]['cue_id'] != ost[-1]['cue_id']
    assert all(not (cue['tc_in'] < bgm['tc_out'] and bgm['tc_in'] < cue['tc_out'])
               for cue in ost for bgm in audio['cues'] if bgm['type'] == 'BGM')


def test_silent_project_keeps_ost_instrumental_without_dialogue(tmp_path):
    from cineforge.audio_design import cues_from_plan
    plan = {'scenes': [{'no': 1, 'title': 'A', 'start': 0, 'end': 10, 'cuts': []}],
            'production_spec': {'bgm': 'piano'}}
    silent = cues_from_plan([], plan, silent=True)
    assert {c['type'] for c in silent} >= {'OST', 'BGM', 'AMBIENCE'}
    assert all(c.get('vocal') is False for c in silent if c['type'] == 'OST')
    assert not [c for c in silent if c['type'] == 'DIALOGUE']


def test_sfx_is_scheduled_from_cut_action_and_dialogue():
    from cineforge.audio_design import cues_from_plan
    plan = {'scenes': [{'no': 1, 'title': 'A', 'start': 0, 'end': 12, 'cuts': []}],
            'production_spec': {'bgm': 'piano'}}
    cuts = [{'cut_id': 'S01C01', 'start': 1.0, 'end': 3.0, 'sound': '액자 유리 긁히는 소리', 'dialogue': None},
            {'cut_id': 'S01C02', 'start': 3.0, 'end': 6.0, 'sound': '대사 + 앰비언스', 'dialogue': '사진은 좋아해',
             'speaker': 'CH01'}]
    rows = cues_from_plan(cuts, plan, False)
    sfx = [row for row in rows if row['type'] == 'SFX']
    assert [row['cut_id'] for row in sfx] == ['S01C01']
    assert sfx[0]['tc_in'] == 1.0 and sfx[0]['tc_out'] == 3.0
    assert '사진은 좋아해' in next(row['description'] for row in rows if row['type'] == 'DIALOGUE')
