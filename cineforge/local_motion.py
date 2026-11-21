"""Bounded local motion renderer. Never evaluates text as FFmpeg syntax."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

FPS = 30
WIDTH, HEIGHT = 720, 1280
RECIPES = {'ui_state', 'kinetic_type'}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frames(seconds: float) -> int:
    n = seconds * FPS
    if not math.isfinite(n) or abs(n - round(n)) > 1e-6:
        raise ValueError('motion timing must align to the 30 fps grid')
    return round(n)


def has_local_motion(plan: dict) -> bool:
    choice = plan.get('production_spec', {}).get('motion_recipe') or {}
    return choice.get('recipe') in RECIPES and any(
        'motion' in cut for scene in plan.get('scenes', []) for cut in scene['cuts']
    )


def compile_plan(plan: dict) -> tuple[str, list[tuple[int, dict]]]:
    recipe = (plan['production_spec'].get('motion_recipe') or {}).get('recipe')
    if recipe not in RECIPES:
        raise ValueError('local motion supports ui_state and kinetic_type only')
    if not plan['production_spec']['aspect'].startswith('9:16'):
        raise ValueError('local motion supports 9:16 only')
    spec = plan['production_spec']
    if any(spec.get(key, '').strip().lower() not in ('', '없음', 'none', 'n/a', '비적용') for key in ('bgm','sfx')):
        raise ValueError('local motion v1 cannot render planned BGM or SFX')
    result = []
    cursor = 0
    for scene in plan['scenes']:
        if _frames(scene['start']) != cursor:
            raise ValueError('non-contiguous motion scenes')
        for cut in scene['cuts']:
            count = _frames(cut['duration'])
            data = cut.get('motion')
            if not isinstance(data, dict) or count < FPS:
                raise ValueError('motion data and at least one second per cut required')
            if cut.get('dialogue') or cut.get('sound') or data.get('audio_cue'):
                raise ValueError('local motion v1 is silent; remove or route audio separately')
            fields = ('headline', 'detail') if recipe == 'kinetic_type' else ('headline',)
            interactive = recipe == 'ui_state' and any(k in data for k in ('option','reply','select_frame','reply_frame'))
            if interactive:
                fields += ('option', 'reply')
                sel, reply = data.get('select_frame'), data.get('reply_frame')
                if type(sel) is not int or type(reply) is not int or not 0 < sel < reply <= count - FPS:
                    raise ValueError('UI must select before replying and hold reply for at least 30 frames')
            allowed = set(fields) | ({'select_frame','reply_frame'} if interactive else set())
            if set(data) != allowed or any(not isinstance(data.get(k), str) or not data[k].strip() or len(data[k]) > 48 or any(ord(c) < 32 for c in data[k]) for k in fields):
                raise ValueError('invalid motion text fields (single line, up to 48 characters)')
            cursor += count
            result.append((count, data))
        if _frames(scene['end']) != cursor:
            raise ValueError('motion scene duration mismatch')
    if not result or cursor != _frames(plan['meta']['runtime_s']) or cursor > 60 * FPS:
        raise ValueError('invalid motion runtime (maximum 60 seconds)')
    return recipe, result


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    run = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=180)
    if run.returncode:
        raise ValueError(f'{args[0]} failed: {run.stderr[-500:]}')
    return run


def render(root: Path, font: Path, *, reviewed_hash: str | None = None) -> dict:
    plan_path = root/'plan.json'
    raw = plan_path.read_bytes()
    recipe, cuts = compile_plan(json.loads(raw))
    plan_hash = hashlib.sha256(raw).hexdigest()
    if reviewed_hash is not None and reviewed_hash != plan_hash:
        raise ValueError('motion plan changed since preproduction review')
    if not font.is_file():
        raise ValueError('supply an installed font file with --font')
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            raise ValueError(f'{tool} is required for local motion')
    qa = root/'qa'
    qa.mkdir(exist_ok=True)
    ff = ['ffmpeg','-v','error','-nostdin','-y']
    with TemporaryDirectory(dir=qa) as name:
        work = Path(name)
        shutil.copyfile(font, work/'font.ttf')
        for i,(count,data) in enumerate(cuts):
            filters = ['drawbox=x=55:y=135:w=610:h=3:color=0x91b7ae:t=fill']

            def draw(field, y, size, color, extra=''):
                (work/f'{field}.txt').write_text(data[field], encoding='utf-8')
                filters.append(f'drawtext=fontfile=font.ttf:textfile={field}.txt:expansion=none:x=56:y={y}:fontsize={size}:fontcolor={color}{extra}')

            def size(field, maximum):
                return min(maximum, 602 // len(data[field]))

            if recipe == 'ui_state':
                draw('headline', 245, size('headline',54), 'white')
                if 'reply' in data:
                    filters.append('drawbox=x=50:y=550:w=620:h=104:color=0x263242:t=fill')
                    filters.append(f"drawbox=x=50:y=550:w=620:h=104:color=0xaaf5cb:t=fill:enable='gte(n,{data['select_frame']})'")
                    draw('option', 585, size('option',37), 'white', f":enable='lt(n,{data['select_frame']})'")
                    draw('option', 585, size('option',37), '0x101820', f":enable='gte(n,{data['select_frame']})'")
                    draw('reply', 795, size('reply',42), '0xaaf5cb', f":enable='gte(n,{data['reply_frame']})'")
            else:
                draw('headline', "'500+90*pow(max(0,1-n/9),3)'", size('headline',70), '0x1d1932')
                draw('detail', "'660+70*pow(max(0,1-n/12),3)'", size('detail',56), '0x4733a0')
            bg = '0x101820' if recipe == 'ui_state' else '0xfcf270'
            _run(ff+['-f','lavfi','-i',f'color={bg}:s={WIDTH}x{HEIGHT}:r={FPS}', '-vf',','.join(filters),'-frames:v',str(count),'-an','-c:v','libx264','-pix_fmt','yuv420p',f'{i}.mp4'], work)
        (work/'clips.txt').write_text(''.join(f"file '{i}.mp4'\n" for i in range(len(cuts))))
        _run(ff+['-f','concat','-safe','1','-i','clips.txt','-c','copy','-movflags','+faststart','preview.mp4'], work)
        _run(ff+['-xerror','-i','preview.mp4','-f','null','-'], work)
        info = json.loads(_run(['ffprobe','-v','error','-show_streams','-of','json','preview.mp4'], work).stdout)['streams']
        count = sum(n for n,_ in cuts)
        if len(info)!=1 or (info[0]['codec_name'],info[0]['width'],info[0]['height'],info[0]['r_frame_rate'],int(info[0]['nb_frames'])) != ('h264',WIDTH,HEIGHT,'30/1',count):
            raise ValueError('motion output failed technical QA')
        if _digest(plan_path) != plan_hash:
            raise ValueError('motion plan changed during render')
        dest = qa/'motion-preview.mp4'
        (work/'preview.mp4').replace(dest)
    report = {'recipe':recipe,'frames':count,'fps':FPS,'width':WIDTH,'height':HEIGHT,'audio':False,'decode':'pass', 'preview':'qa/motion-preview.mp4','sha256':_digest(dest),'plan_sha256':plan_hash,'human_review':False}
    (qa/'motion-report.json').write_text(json.dumps(report, indent=2))
    return report


def deliver(root: Path, approved_hash: str) -> dict:
    report = json.loads((root/'qa/motion-report.json').read_text())
    video = root/'qa/motion-preview.mp4'
    if len(approved_hash) != 64 or approved_hash != report['sha256'] or approved_hash != _digest(video) or report['plan_sha256'] != _digest(root/'plan.json') or report['decode'] != 'pass':
        raise ValueError('motion approval or input/output hash mismatch')
    target = root/'final'
    target.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=target) as name:
        temp = Path(name)/'motion.mp4'
        shutil.copyfile(video,temp)
        if _digest(temp) != approved_hash:
            raise ValueError('motion preview changed during delivery')
        temp.replace(target/'motion.mp4')
    result = {**report,'human_review':True,'video':'final/motion.mp4'}
    (target/'motion-delivery.json').write_text(json.dumps(result,indent=2))
    return result
