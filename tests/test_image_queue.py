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
