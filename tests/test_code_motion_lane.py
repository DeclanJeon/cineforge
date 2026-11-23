"""Local code-motion lane: zero-cost execution scope, envelope tool, receipts and motion_brief schema."""
import json
import subprocess

import pytest

from cineforge import execution_plan
from cineforge.cli import main
from cineforge.jobs import Job, JobError, record_results, video_jobs, write_envelope
from cineforge.schemas import validate
from closure_fixture import prepared


def scope(tmp_path, lanes):
    path = tmp_path / 'scope.json'
    path.write_text(json.dumps({'lanes': lanes}))
    return path


def approve_code_motion(project, tmp_path, capsys, max_jobs=60, **options):
    path = scope(tmp_path, [{'kind': 'video_cut', 'provider': 'code-motion', 'model': 'html-seek-v1', 'max_jobs': max_jobs, **options}])
    capsys.readouterr()
    assert main(['execution-plan', str(project.root), '--file', str(path)]) == 0
    digest = json.loads(capsys.readouterr().out)['plan_hash']
    assert main(['authorize', str(project.root), '--approve-plan', digest]) == 0
    return digest


def test_code_motion_lane_needs_no_cost_fields(tmp_path, capsys):
    project = prepared(tmp_path)
    approve_code_motion(project, tmp_path, capsys)
    lane = execution_plan.read(project.root)['lanes']['video_cut']
    assert lane == {'kind': 'video_cut', 'provider': 'code-motion', 'model': 'html-seek-v1', 'max_jobs': 60}


def test_code_motion_lane_rejects_cost_fields_and_other_kinds(tmp_path, capsys):
    project = prepared(tmp_path)
    with_cost = scope(tmp_path, [{'kind': 'video_cut', 'provider': 'code-motion', 'model': 'm', 'max_jobs': 1,
                                  'unit': 'usd', 'estimate': '1', 'ceiling': '2'}])
    assert main(['execution-plan', str(project.root), '--file', str(with_cost)]) == 1
    other = scope(tmp_path, [{'kind': 'bgm', 'provider': 'code-motion', 'model': 'm', 'max_jobs': 1}])
    assert main(['execution-plan', str(project.root), '--file', str(other)]) == 1
    assert 'invalid_execution_lane' in capsys.readouterr().err


def test_code_motion_envelope_and_receipt(tmp_path, capsys):
    project = prepared(tmp_path)
    approve_code_motion(project, tmp_path, capsys)
    jobs = video_jobs(project.root)
    assert jobs and all(job.provider == 'code-motion' and job.tool == 'render_html_motion' for job in jobs)
    envelope = json.loads(write_envelope(project.root, 'S08_video', jobs).read_text())
    assert envelope['authority']['quotes'] == {}
    out = project.root / 'renders' / 'c1.mp4'
    out.parent.mkdir()
    seconds = dict(jobs[0].params)['duration_s']
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    f'color=s=90x160:r=30:d={seconds}', '-c:v', 'libx264', str(out)], check=True)
    first = jobs[0].job_id
    record_results(project.root, 'S08_video', [{'job_id': first, 'status': 'accepted', 'path': 'renders/c1.mp4'}],
                   runner_meta='code-motion')
    receipt = json.loads((project.root / 'receipts/S08_video.json').read_text())
    assert receipt['results'][first]['provider_meta'] == 'code-motion'
    out.write_bytes(b'changed')
    with pytest.raises(JobError, match='receipt_conflict'):
        record_results(project.root, 'S08_video', [{'job_id': first, 'status': 'accepted', 'path': 'renders/c1.mp4'}])


def test_code_motion_scope_still_enforced(tmp_path, capsys):
    project = prepared(tmp_path)
    approve_code_motion(project, tmp_path, capsys, max_jobs=1)
    job = Job('v1', 'video_cut', 'code-motion', 'render_html_motion', (), 'p', (('model', 'html-seek-v1'),))
    with pytest.raises(JobError, match='execution_scope_changed'):
        write_envelope(project.root, 'S08_video',
                       (job, Job('v2', 'video_cut', 'code-motion', 'render_html_motion', (), 'p', job.params)))


def test_mixed_cut_scope_and_receipt(tmp_path, capsys):
    from cineforge.video_jobs import select_take

    project = prepared(tmp_path)
    row, other, *_ = project.read('assets/video_prompts.json')['prompts']
    cut = row['cut_id']
    approve_code_motion(project, tmp_path, capsys, max_jobs=1, cut_ids=[cut])
    jobs = video_jobs(project.root)
    assert [job.job_id for job in jobs] == [f'video:{cut}']
    write_envelope(project.root, 'S08_video', jobs)
    path = project.root / 'clip.mp4'
    seconds = row['params']['duration_s']
    result = [{'job_id': jobs[0].job_id, 'status': 'accepted', 'path': path.name}]
    for width, height in [(160, 90), (90, 160)]:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        f'color=s={width}x{height}:r=30:d={seconds}', '-c:v', 'libx264', str(path)], check=True)
        if width > height:
            with pytest.raises(JobError, match='aspect'):
                record_results(project.root, 'S08_video', result)
            assert not (project.root / 'receipts/S08_video.json').exists()
    with pytest.raises(JobError, match='code_motion_take'):
        select_take(project.root, cut, path.name)
    record_results(project.root, 'S08_video', result)
    assert select_take(project.root, cut, path.name)['path'] == path.name
    with pytest.raises(JobError, match='code_motion_take'):
        select_take(project.root, other['cut_id'], path.name)
    path.write_bytes(b'modified')
    with pytest.raises(JobError, match='code_motion_take'):
        select_take(project.root, cut, path.name)


BRIEF = {
    'analysis': {'audience_task': '앱의 핵심 행동 이해', 'message_units': ['기록', '분석'], 'format_hint': 'product_film',
                 'platform': '9:16 inferred', 'duration': '30s inferred', 'assets': '[로고]', 'data_sources': 'none',
                 'audio': 'none', 'brand': 'neutral inferred', 'constraints': '', 'delivery': 'render'},
    'candidates': [{'format': 'product_film', 'recipe': 'ui_state', 'reason': '행동→결과', 'scores': {'전달력': '상'}}],
    'choice': {'format': 'product_film', 'recipe': 'ui_state', 'reason': '실제 UI 전이가 핵심'},
    'route_by_cut': [{'cut': 'C01', 'route': 'code'}, {'cut': 'C02', 'route': 'local'}],
}


def plan_with(brief):
    return {'production_spec': {'aspect': '9:16', 'fps': '30fps', 'camera': '', 'lighting': '', 'edit': '',
                                'camera_movement': '', 'bgm': '', 'sfx': '', 'grading': '', 'subtitles': '',
                                'motion_brief': brief}}


def brief_errors(brief):
    return [e for e in validate(plan_with(brief), 'plan') if 'motion_brief' in e]


def test_motion_brief_schema_accepts_valid_brief():
    assert brief_errors(BRIEF) == []


@pytest.mark.parametrize('broken', [
    {**BRIEF, 'route_by_cut': [{'cut': 'C01', 'route': 'cloud'}]},
    {**BRIEF, 'choice': {'format': 'tiktok', 'recipe': 'ui_state', 'reason': 'x'}},
    {k: v for k, v in BRIEF.items() if k != 'analysis'},
    {**BRIEF, 'candidates': []},
    {**BRIEF, 'analysis': {k: v for k, v in BRIEF['analysis'].items() if k != 'delivery'}},
])
def test_motion_brief_schema_rejects_broken_brief(broken):
    assert brief_errors(broken)
