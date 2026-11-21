import json

import pytest

from cineforge.audio_jobs import plan_jobs
from cineforge.jobs import JobError, record_results, write_envelope
from closure_fixture import prepared


def test_stale_envelope_and_receipt_binding_are_refused(tmp_path):
    project = prepared(tmp_path)
    project.grant(execution=True, providers=['suno', 'elevenlabs', 'fish_audio', 'ludyte'])
    jobs = plan_jobs(project.root)
    write_envelope(project.root, 'S08_audio', jobs)
    out = project.root / 'audio/a.wav'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b'RIFFa')
    record_results(project.root, 'S08_audio', [{'job_id': jobs[0].job_id, 'status': 'accepted', 'path': 'audio/a.wav'}])
    sound = json.loads((project.root / 'assets/sound_plan.json').read_text())
    sound['cues'][0]['prompt'] = sound['cues'][0]['prompt'] + ' 변경'
    (project.root / 'assets/sound_plan.json').write_text(json.dumps(sound))
    with pytest.raises(JobError, match='envelope_stale'):
        record_results(project.root, 'S08_audio', [{'job_id': jobs[0].job_id, 'status': 'accepted', 'path': 'audio/a.wav'}])
    write_envelope(project.root, 'S08_audio', plan_jobs(project.root))
    with pytest.raises(JobError, match='receipt_binding_mismatch'):
        record_results(project.root, 'S08_audio', [{'job_id': jobs[0].job_id, 'status': 'accepted', 'path': 'audio/a.wav'}])


def test_uncertain_job_stays_uncertain_across_reruns(tmp_path):
    project = prepared(tmp_path)
    project.grant(execution=True, providers=['suno', 'elevenlabs', 'fish_audio', 'ludyte'])
    jobs = plan_jobs(project.root)
    write_envelope(project.root, 'S08_audio', jobs)
    record_results(project.root, 'S08_audio', [{'job_id': jobs[0].job_id, 'status': 'uncertain', 'error': 'timeout'}])
    write_envelope(project.root, 'S08_audio', jobs)
    receipt = json.loads((project.root / 'receipts/S08_audio.json').read_text())
    assert receipt['results'][jobs[0].job_id]['status'] == 'uncertain'
    with pytest.raises(JobError, match='output_missing'):
        record_results(project.root, 'S08_audio', [{'job_id': jobs[0].job_id, 'status': 'accepted', 'path': 'audio/none.wav'}])
