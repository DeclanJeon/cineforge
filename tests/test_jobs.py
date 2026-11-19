import json

import pytest

from cineforge.cli import main
from cineforge.jobs import (JobError, audio_jobs, binding, load_envelope, record_results, video_jobs,
                            write_envelope)
from cineforge.pipeline import Project
from cineforge.receipts import atomic_text
from conftest import SAMPLE_REQUEST


def _project(tmp_path):
    main(['new', SAMPLE_REQUEST, '--projects-dir', str(tmp_path), '--project-id', 'p', '--provider', 'mock',
          '--no-nonstop', '--until', 'S03_plan'])
    project = Project(tmp_path / 'p')
    project.grant(accept_plan=True, accept_preproduction=True)
    project.run(until='S07_assets')
    png = b'\x89PNG\r\n\x1a\npayload'
    for row in project.read('assets/image_prompts.json')['prompts']:
        out = project.root / 'assets/generated' / (row['prompt_id'] + '.png')
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_text(out, png.decode('latin-1'))
    registry = project.read('assets/asset_registry.json')
    for row in registry['assets']:
        row.update(status='available', path=f'assets/generated/{row["asset_id"]}.png')
        out = project.root / row['path']
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_text(out, png.decode('latin-1'))
    project.write('assets/asset_registry.json', registry, 'asset_registry')
    outputs = {}
    for row in project.read('assets/video_prompts.json')['prompts']:
        for ref in row['refs']:
            out = project.root / 'assets/generated' / (ref + '.png')
            out.parent.mkdir(parents=True, exist_ok=True)
            atomic_text(out, png.decode('latin-1'))
            outputs[ref] = f'assets/generated/{ref}.png'
    project.write('assets/image_outputs.json', outputs)
    return project


def test_audio_jobs_cover_four_lanes_and_are_deterministic(tmp_path):
    project = _project(tmp_path)
    jobs = audio_jobs(project.root)
    kinds = {job.kind for job in jobs}
    assert {'ost', 'bgm', 'sfx', 'dialogue'} <= kinds
    assert all(job.provider in ('suno', 'elevenlabs', 'fish_audio') for job in jobs)
    assert audio_jobs(project.root) == jobs
    assert len({job.job_id for job in jobs}) == len(jobs)
    assert all(job.idempotency_key for job in jobs)


def test_envelope_requires_execution_and_is_stable(tmp_path):
    project = _project(tmp_path)
    with pytest.raises(JobError, match='execution_not_authorized'):
        write_envelope(project.root, 'S08_audio', audio_jobs(project.root))
    project.grant(execution=True, providers=['suno', 'elevenlabs', 'fish_audio', 'ludyte'])
    first = write_envelope(project.root, 'S08_audio', audio_jobs(project.root))
    before = first.read_text()
    assert write_envelope(project.root, 'S08_audio', audio_jobs(project.root)).read_text() == before
    assert load_envelope(project.root, 'S08_audio')['stage'] == 'S08_audio'
    sound = json.loads((project.root / 'assets/sound_plan.json').read_text())
    sound['cues'][0]['prompt'] += ' 변경'
    (project.root / 'assets/sound_plan.json').write_text(json.dumps(sound))
    with pytest.raises(JobError, match='envelope_stale'):
        load_envelope(project.root, 'S08_audio')


def test_video_jobs_pin_ready_images_and_durations(tmp_path):
    project = _project(tmp_path)
    jobs = video_jobs(project.root)
    assert jobs and all(job.kind == 'video_cut' and job.provider == 'ludyte' for job in jobs)
    assert all(float(dict(job.params)['duration_s']) > 0 for job in jobs)
    assert all(job.inputs for job in jobs)


def test_receipts_are_idempotent_and_reject_tampering(tmp_path):
    project = _project(tmp_path)
    project.grant(execution=True, providers=['suno', 'elevenlabs', 'fish_audio', 'ludyte'])
    jobs = audio_jobs(project.root)
    write_envelope(project.root, 'S08_audio', jobs)
    job = jobs[0]
    out = project.root / 'audio' / 'q001.wav'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b'RIFFfake')
    result = record_results(project.root, 'S08_audio', [{'job_id': job.job_id, 'status': 'accepted', 'path': 'audio/q001.wav'}])
    first = json.loads(result.read_text())
    assert first['results'][job.job_id]['sha256'] and first['results'][job.job_id]['path'] == 'audio/q001.wav'
    record_results(project.root, 'S08_audio', [{'job_id': job.job_id, 'status': 'accepted', 'path': 'audio/q001.wav'}])
    with pytest.raises(JobError, match='output_missing'):
        record_results(project.root, 'S08_audio', [{'job_id': job.job_id, 'status': 'accepted', 'path': 'audio/none.wav'}])
    out.write_bytes(b'RIFFother')
    with pytest.raises(JobError, match='receipt_conflict'):
        record_results(project.root, 'S08_audio', [{'job_id': job.job_id, 'status': 'accepted', 'path': 'audio/q001.wav'}])


def test_uncertain_and_rejected_are_recorded_without_retry(tmp_path):
    project = _project(tmp_path)
    project.grant(execution=True, providers=['suno', 'elevenlabs', 'fish_audio', 'ludyte'])
    jobs = audio_jobs(project.root)
    write_envelope(project.root, 'S08_audio', jobs)
    record_results(project.root, 'S08_audio', [{'job_id': jobs[0].job_id, 'status': 'uncertain', 'error': 'stream closed'},
                                               {'job_id': jobs[1].job_id, 'status': 'rejected', 'error': 'policy'}])
    receipt = json.loads((project.root / 'receipts/S08_audio.json').read_text())['results']
    assert receipt[jobs[0].job_id]['status'] == 'uncertain'
    assert receipt[jobs[1].job_id]['status'] == 'rejected'
    with pytest.raises(JobError, match='output_missing'):
        record_results(project.root, 'S08_audio', [{'job_id': jobs[0].job_id, 'status': 'accepted', 'path': 'audio/x.wav'}])
