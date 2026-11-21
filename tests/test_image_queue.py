import threading
import time
from pathlib import Path

import pytest
from cineforge.cli import main
from cineforge.pipeline import Project
from conftest import SAMPLE_REQUEST


def test_default_nonstop_and_scope(tmp_path):
    main(['new', SAMPLE_REQUEST, '--projects-dir',str(tmp_path),'--project-id','p','--provider','mock'])
    p = Project(tmp_path/'p')
    assert p.progress()['stages']['G2_preproduction_review']['status'] == 'done'
    assert not p.authority()['execution']


def test_cli_generates_images_without_authorizing_video(tmp_path, monkeypatch):
    import cineforge.image_queue as iq
    calls = []
    def local(row, refs, output, *, supervisor_fd):
        calls.append(row["prompt_id"])
        assert all(path.is_file() for path in refs)
        output.write_bytes(PNG)
    monkeypatch.setattr(iq, 'codex_imagen', local)
    main(['new', SAMPLE_REQUEST, '--projects-dir',str(tmp_path),'--project-id','p','--provider','mock','--image-limit','100'])
    p = Project(tmp_path/'p')
    images = p.read('assets/image_outputs.json')
    assert images and set(calls)==set(images)
    assert not p.authority()['execution']
    count = len(calls)
    p.run()
    assert len(calls)==count

def test_scoped_video_plan_prepares_approved_images_before_video_envelope(tmp_path, monkeypatch):
    from cineforge import execution_plan, image_queue
    from cineforge.video_jobs import plan_jobs

    calls = []

    def local(row, refs, output, *, supervisor_fd):
        assert all(ref.is_file() for ref in refs)
        calls.append(row['prompt_id'])
        output.write_bytes(PNG)

    monkeypatch.setattr(image_queue, 'codex_imagen', local)
    assert main(['new', SAMPLE_REQUEST, '--projects-dir', str(tmp_path), '--project-id', 'p',
                 '--provider', 'mock', '--until', 'G2_preproduction_review']) == 0
    project = Project(tmp_path / 'p')
    plan = execution_plan.proposal(project, {'lanes': [
        {'kind': 'video_cut', 'provider': 'ludyte', 'model': 'singularity-full-v2', 'max_jobs': 100},
    ]})
    count = len(project.read('assets/image_prompts.json')['prompts'])
    project.grant(image_limit=count - 1)
    project.run(until='S08_generation')
    assert not calls
    execution_plan.approve(project, plan['plan_hash'], 1)
    project.run(until='S08_generation')
    assert project.progress()['stages']['S08_generation']['status'] == 'blocked'
    assert not calls
    project.grant(image_limit=count)
    project.set_stage(project.progress(), 'S08_generation', 'waiting_external', 'old scoped handoff')
    project.run(until='S08_generation')
    assert len(calls) == count
    assert project.progress()['stages']['S08_generation']['status'] == 'waiting_external'
    assert plan_jobs(project.root)
    assert not (project.root / 'handoffs/S08_generation.json').exists()
    project.run(until='S08_generation')
    assert len(calls) == count


def test_dependency_queue_cap_reuse_and_uncertainty(tmp_path):
    from cineforge.image_queue import generate
    active = peak = 0
    lock = threading.Lock()
    calls = []
    rows = [dict(prompt_id=f'I{i}',prompt=str(i),refs=[]) for i in range(8)]
    rows.append(dict(prompt_id='cut',prompt='cut',refs=['I7']))
    def execute(row, refs, output):
        nonlocal active,peak
        with lock:
            calls.append(row['prompt_id'])
            active += 1
            peak = max(peak,active)
        if row['refs']:
            assert refs[0].is_file()
        time.sleep(.03)
        output.write_bytes(PNG)
        with lock:
            active -= 1
    paths = generate(tmp_path,rows,9,execute)
    assert peak == 5 and len(paths)==9
    assert generate(tmp_path,rows,9,execute)==paths and len(calls)==9
    with pytest.raises(ValueError):
        generate(tmp_path,rows+[dict(prompt_id='extra',prompt='x',refs=[])],9,execute)
    def fail(*args):
        raise ValueError('uncertain')
    with pytest.raises(ValueError):
        generate(tmp_path,[dict(prompt_id='extra',prompt='x',refs=[])],10,fail)
    with pytest.raises(ValueError):
        generate(tmp_path,[dict(prompt_id='extra',prompt='x',refs=[])],10,execute)
    assert len(calls)==9

import base64
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlGAAAAAASUVORK5CYII=')
