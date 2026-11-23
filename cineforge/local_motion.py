"""Bounded local motion renderer. Never evaluates text as FFmpeg syntax."""
from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

FPS = 30
WIDTH, HEIGHT = 720, 1280
RECIPES = {'ui_state', 'kinetic_type', 'echo_type', 'diagram_data', 'shape_morph', 'card_sequence',
           'image_reveal', 'chart_bars', 'paper_layers', 'map_route', 'pose_swap'}
CARD_SLIDE_FRAMES = 8
# Canvas, primary ink, secondary ink, decorative accent.
POSTER_PALETTES = {
    'editorial': ('f4efe6', '202b2b', '36474a', 'ad5444'),
    'pop': ('ffdd65', '221736', '48316f', 'ea5a68'),
    'dark': ('152131', 'f8f6ee', 'bbebdc', '68d0ac'),
}
SHAPE_SIZE = 200
SHAPE_RADII = {'square': 0, 'rounded_square': 40, 'circle': 100}


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
        raise ValueError('local motion recipe not supported')
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
            fields = ('headline', 'detail') if recipe in ('kinetic_type', 'shape_morph') else ('headline',)
            interactive = recipe == 'ui_state' and any(k in data for k in ('option','reply','select_frame','reply_frame'))
            if interactive:
                fields += ('option', 'reply')
                sel, reply = data.get('select_frame'), data.get('reply_frame')
                if type(sel) is not int or type(reply) is not int or not 0 < sel < reply <= count - FPS:
                    raise ValueError('UI must select before replying and hold reply for at least 30 frames')
            allowed = set(fields) | ({'select_frame','reply_frame'} if interactive else set())
            if recipe == 'diagram_data':
                allowed |= {'steps', 'reveal_frames'}
                steps, frames = data.get('steps'), data.get('reveal_frames')
                if not isinstance(steps, list) or not 2 <= len(steps) <= 3 or not all(_valid_text(s, 28) for s in steps):
                    raise ValueError('diagram requires two or three single-line step labels')
                if (not isinstance(frames, list) or len(frames) != len(steps)
                        or any(type(n) is not int for n in frames) or frames[0] < 0
                        or any(b <= a for a, b in zip(frames, frames[1:])) or frames[-1] > count - FPS):
                    raise ValueError('diagram reveal frames must increase and hold the full sequence for at least 30 frames')
            if recipe == 'shape_morph':
                allowed |= {'from_shape', 'to_shape', 'morph_start_frame', 'morph_end_frame'}
                names = (data.get('from_shape'), data.get('to_shape'))
                if any(not isinstance(name, str) or name not in SHAPE_RADII for name in names) or names[0] == names[1]:
                    raise ValueError('shape morph needs two distinct supported shapes')
                start, end = data.get('morph_start_frame'), data.get('morph_end_frame')
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= count - FPS or end - start < 2:
                    raise ValueError('shape morph must span at least two frames and hold the result for one second')
            if recipe == 'card_sequence':
                allowed |= {'layout', 'cards', 'reveal_frames'}
                layout, cards, frames = data.get('layout'), data.get('cards'), data.get('reveal_frames')
                if layout not in ('stack', 'carousel', 'compare') or not isinstance(cards, list) or not 2 <= len(cards) <= 3:
                    raise ValueError('card sequence requires two or three text cards and a supported layout')
                if layout == 'compare' and len(cards) != 2:
                    raise ValueError('card comparison requires exactly two peer cards')
                if not all(_valid_text(card, 12 if layout == 'compare' else 24) for card in cards):
                    raise ValueError('card labels exceed the single-line limit')
                if (not isinstance(frames, list) or len(frames) != len(cards)
                        or any(type(n) is not int for n in frames) or frames[0] < 0
                        or any(b <= a for a,b in zip(frames, frames[1:]))):
                    raise ValueError('card reveal frames must increase')
                durations = (b-a for a,b in zip(frames, frames[1:]+[count]))
                if (layout == 'carousel' and any(n < FPS + CARD_SLIDE_FRAMES for n in durations)) or count - frames[-1] < FPS:
                    raise ValueError('card reading hold requires at least one second after movement')
            if recipe == 'image_reveal':
                allowed |= {'asset_id', 'at_frame', 'mode', 'image_layout', 'detail'}
                asset, at = data.get('asset_id'), data.get('at_frame')
                if (not isinstance(asset, str) or not asset.strip() or type(at) is not int or at < 0
                        or data.get('mode') not in ('fade', 'slide', 'wipe')
                        or data.get('image_layout') not in ('logo', 'photo', 'screen') or at > count-FPS):
                    raise ValueError('image reveal needs a registered asset id, a supported mode and a hold before the cut ends')
            if recipe == 'chart_bars':
                allowed |= {'bars', 'max_value', 'source', 'detail'}
                bars, top, source = data.get('bars'), data.get('max_value'), data.get('source')
                if (not isinstance(bars, list) or not 2 <= len(bars) <= 4
                        or not isinstance(top, (int, float)) or isinstance(top, bool) or not 0 < top <= 1_000_000
                        or not _valid_text(source, 60) or not all(
                            isinstance(b, dict) and set(b) == {'label', 'value'} and _valid_text(b['label'], 12)
                            and isinstance(b['value'], (int, float)) and not isinstance(b['value'], bool)
                            and 0 <= b['value'] <= top for b in bars)):
                    raise ValueError('chart bars need two to four labelled values, a positive maximum and a recorded source')
            if recipe == 'pose_swap':
                allowed |= {'poses', 'at_frame'}
                poses, at = data.get('poses'), data.get('at_frame')
                if (not isinstance(poses, list) or len(poses) != 2 or not all(isinstance(x, str) and x.strip() for x in poses)
                        or type(at) is not int or not 0 < at <= count-FPS):
                    raise ValueError('pose swap needs two registered poses and a hold before the cut ends')
            if recipe == 'echo_type':
                allowed |= {'phrases', 'reveal_frames'}
                phrases, frames = data.get('phrases'), data.get('reveal_frames')
                if (not isinstance(phrases, list) or not 2 <= len(phrases) <= 3 or not all(_valid_text(p, 24) for p in phrases)
                        or not isinstance(frames, list) or len(frames) != len(phrases)
                        or any(type(n) is not int for n in frames) or frames[0] < 0
                        or any(b-a < 8 for a,b in zip(frames, frames[1:])) or frames[-1] > count-FPS):
                    raise ValueError('echo type needs two or three phrases with spaced reveals and a settled hold')
            if recipe == 'paper_layers':
                allowed |= {'layers', 'reveal_frames'}
                layers, frames = data.get('layers'), data.get('reveal_frames')
                if (not isinstance(layers, list) or not 2 <= len(layers) <= 3 or not all(_valid_text(x, 20) for x in layers)
                        or not isinstance(frames, list) or len(frames) != len(layers)
                        or any(type(n) is not int for n in frames) or frames[0] < 0
                        or any(b-a < 12 for a,b in zip(frames, frames[1:])) or frames[-1] > count-FPS):
                    raise ValueError('paper layers need two or three labels, increasing frames and a settled hold')
            if recipe == 'map_route':
                allowed |= {'asset_id', 'route', 'reveal_frames'}
                points, frames = data.get('route'), data.get('reveal_frames')
                if not isinstance(data.get('asset_id'), str) or not data['asset_id'].strip():
                    raise ValueError('map route needs a registered map asset')
                if (not isinstance(points, list) or not 2 <= len(points) <= 4
                        or not all(isinstance(pt, list) and len(pt) == 2 and all(isinstance(v,(int,float)) and not isinstance(v,bool) and 0 <= v <= 1 for v in pt) for pt in points)):
                    raise ValueError('map route needs two to four normalized points')
                if (not isinstance(frames, list) or len(frames) != len(points)-1
                        or any(type(n) is not int for n in frames) or frames[0] < 0
                        or any(b <= a for a,b in zip(frames, frames[1:])) or frames[-1] > count-FPS):
                    raise ValueError('map route frames must match segments and leave a settled hold')
            if 'loop' in data:
                allowed.add('loop')
                if data['loop'] is not True:
                    raise ValueError('loop must be the boolean true')
            if 'poster' in data:
                allowed.add('poster')
                if recipe != 'kinetic_type' or not isinstance(data['poster'], str) or data['poster'] not in POSTER_PALETTES:
                    raise ValueError('poster preset requires kinetic type and a supported palette')
            if 'type_reveal' in data:
                allowed.add('type_reveal')
                reveal = data['type_reveal']
                if recipe != 'kinetic_type' or not isinstance(reveal, dict) or set(reveal) != {'phrases', 'reveal_frames'}:
                    raise ValueError('type reveal is only supported on kinetic type cuts')
                phrases, frames = reveal['phrases'], reveal['reveal_frames']
                if not isinstance(phrases, list) or not 2 <= len(phrases) <= 3 or not all(_valid_text(p, 24) for p in phrases):
                    raise ValueError('type reveal requires two or three short whole phrases')
                if (not isinstance(frames, list) or len(frames) != len(phrases)
                        or any(type(n) is not int for n in frames) or frames[0] < 0
                        or any(b-a < 6 for a,b in zip(frames,frames[1:])) or frames[-1] > count-FPS-6):
                    raise ValueError('type reveal needs six frames between cues and a 30-frame settled hold')
            if 'connector_frames' in data:
                allowed.add('connector_frames')
                span = data['connector_frames']
                if (recipe != 'diagram_data' or type(span) is not int or span < 2
                        or any(b-a < span for a,b in zip(data['reveal_frames'], data['reveal_frames'][1:]))):
                    raise ValueError('connector must draw between adjacent diagram reveals')
            if 'burst' in data:
                allowed.add('burst')
                burst = data['burst']
                if (not interactive or not isinstance(burst, dict) or set(burst) != {'at_frame', 'seed'}
                        or any(type(burst[key]) is not int for key in burst)
                        or not 0 <= burst['seed'] <= 65535
                        or not data['reply_frame'] <= burst['at_frame'] <= count-24):
                    raise ValueError('burst requires a UI reply, a seed, and 24 frames after the reply trigger')
            if 'entrance' in data:
                allowed.add('entrance')
                entrance = data['entrance']
                if (not isinstance(entrance, dict) or set(entrance) != {'kind', 'duration_frames'}
                        or entrance['kind'] not in ('wipe_left', 'wipe_right')
                        or type(entrance['duration_frames']) is not int):
                    raise ValueError('invalid motion entrance')
                duration = entrance['duration_frames']
                if not 2 <= duration <= count - FPS:
                    raise ValueError('wipe must last at least two frames and hold full image for one second')
                first_action = (data['select_frame'] if interactive else data['reveal_frames'][0] if recipe in ('diagram_data', 'card_sequence')
                                else data['morph_start_frame'] if recipe == 'shape_morph' else count)
                if 'type_reveal' in data:
                    first_action = data['type_reveal']['reveal_frames'][0]
                if duration > first_action:
                    raise ValueError('wipe must finish before the first action is obscured')
            if set(data) - allowed or any(not _valid_text(data.get(k), 48) for k in fields):
                raise ValueError('invalid motion text fields (single line, up to 48 characters)')
            cursor += count
            result.append((count, data))
        if _frames(scene['end']) != cursor:
            raise ValueError('motion scene duration mismatch')
    if not result or cursor != _frames(plan['meta']['runtime_s']) or cursor > 60 * FPS:
        raise ValueError('invalid motion runtime (maximum 60 seconds)')
    return recipe, result


def _valid_text(value: object, limit: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit and all(ord(c) >= 32 for c in value)


def shape_tile(data: dict, frame: int) -> bytes:
    """Interpolate corner radius around one fixed, centered silhouette."""
    start, end = data['morph_start_frame'], data['morph_end_frame']
    fraction = min(1, max(0, (frame-start)/(end-start)))
    eased = fraction*fraction*(3-2*fraction)
    a, b = (SHAPE_RADII[data[key]] for key in ('from_shape', 'to_shape'))
    radius = a + (b-a)*eased
    bg, fg = bytes.fromhex('101820'), bytes.fromhex('AAF5CB')
    rows = bytearray()
    for y in range(SHAPE_SIZE):
        edge = min(y+.5, SHAPE_SIZE-y-.5)
        inset = round(radius-math.sqrt(radius*radius-(radius-edge)**2)) if edge < radius else 0
        rows.extend(bg*inset + fg*(SHAPE_SIZE-2*inset) + bg*inset)
    return bytes(rows)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    run = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=180)
    if run.returncode:
        raise ValueError(f'{args[0]} failed: {run.stderr[-500:]}')
    return run


def render(root: Path, font: Path, *, reviewed_hash: str | None = None) -> dict:
    from .project_skills import require_pack

    require_pack(root)
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
            palette = POSTER_PALETTES.get(data.get('poster'))
            ink, secondary = ('0x'+palette[1], '0x'+palette[2]) if palette else ('0x1d1932', '0x4733a0')
            accent = '0x'+palette[3] if palette else '0x91b7ae'
            filters = [f'drawbox=x=55:y=135:w=610:h=3:color={accent}:t=fill']
            if palette:
                filters.extend([
                    f'drawbox=x=55:y=112:w=110:h=12:color={accent}:t=fill',
                    f'drawbox=x=55:y=1155:w=610:h=4:color={accent}:t=fill',
                    f'drawbox=x=623:y=1175:w=42:h=42:color={accent}:t=fill',
                ])

            def draw(field, y, size, color, extra='', *, value=None, x=56):
                (work/f'{field}.txt').write_text(data[field] if value is None else value, encoding='utf-8')
                filters.append(f'drawtext=fontfile=font.ttf:textfile={field}.txt:expansion=none:x={x}:y={y}:fontsize={size}:fontcolor={color}{extra}')

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
                    if burst := data.get('burst'):
                        rng = random.Random(burst['seed'])
                        for j in range(18):
                            angle = rng.uniform(-.7,.7) + (math.pi if j%2 else 0)
                            for phase in range(3):
                                r = 48 + phase*56 + rng.randrange(0,24)
                                x, y = round(360+math.cos(angle)*r), round(1035+math.sin(angle)*r)
                                n = burst['at_frame'] + phase*8 + j%3
                                end = min(burst['at_frame']+24, n+6)
                                color = '0xaaf5cb' if j%2 else '0xffeb94'
                                filters.append(f"drawbox=x={x}:y={y}:w=6:h=6:color={color}:t=fill:enable='gte(n,{n})*lt(n,{end})'")
            elif recipe == 'image_reveal':
                draw('headline', 245, size('headline', 54), 'white')
                filters.append('drawbox=x=100:y=400:w=520:h=520:color=0x3b4b56:t=3')
                draw('caption', 1000, 26, '0xaaf5cb', f":enable='gte(n,{data['at_frame']})'",
                     value={'logo':'승인된 마크 공개','photo':'제공된 사진','screen':'제공된 화면'}[data['image_layout']])
                if data.get('detail'):
                    draw('detail', 1050, size('detail', 38), 'white', f":enable='gte(n,{data['at_frame']})'")
            elif recipe == 'chart_bars':
                draw('headline', 245, size('headline', 54), 'white')
                bars, top = data['bars'], float(data['max_value'])
                width = 520 // len(bars)
                for j, bar in enumerate(bars):
                    height = round(420 * float(bar['value']) / top)
                    at = 12 + j*6
                    x = 80 + j*width
                    filters.append(f"drawbox=x={x}:y={960-height}:w={width-28}:h={height}:color=0xaaf5cb:t=fill:enable='gte(n,{at})'")
                    draw(f'bar{j}', 975, 24, 'white', value=f"{bar['value']:g}", x=x)
                    draw(f'label{j}', 1015, min(24, 180//len(bar['label'])), '0xb5c2cb', value=bar['label'], x=x)
                draw('source', 1115, 20, '0x91a3ad', value=f"출처: {data['source']}")
            elif recipe == 'echo_type':
                draw('headline', 245, size('headline', 54), 'white')
                inks = ('0xaaf5cb', '0x55717c', '0xffeb94')
                for j,(phrase, at) in enumerate(zip(data['phrases'], data['reveal_frames'], strict=True)):
                    filters.append(f"drawbox=x=56+{j*18}:y={520+150*j}:w=520:h=4:color={inks[j]}:t=fill:enable='gte(n,{at})'")
                    draw(f'echo{j}', 380+150*j, min(64, 520//len(phrase)), inks[j], f":enable='gte(n,{at})'", value=phrase, x=56+j*18)
            elif recipe == 'paper_layers':
                draw('headline', 245, size('headline', 54), 'white')
                tints = ('0x2f4550', '0x3b5560', '0x486a72')
                for j,(label, at) in enumerate(zip(data['layers'], data['reveal_frames'], strict=True)):
                    x, y = 86+j*36, 430+j*150
                    show = f":enable='gte(n,{at})'"
                    filters.append(f'drawbox=x={x+10}:y={y+12}:w=500:h=310:color=0x0b1216:t=fill{show}')
                    filters.append(f'drawbox=x={x}:y={y}:w=500:h=310:color={tints[j]}:t=fill{show}')
                    filters.append(f'drawbox=x={x}:y={y}:w=500:h=6:color=0xaaf5cb:t=fill{show}')
                    draw(f'layer{j}', y+120, min(46,420//len(label)), 'white', show, value=label, x=x+34)
            elif recipe == 'map_route':
                draw('headline', 245, size('headline', 54), 'white')
                for j in range(len(data['route'])-1):
                    frames = data['reveal_frames']
                    steps = 8 if j == 0 else 4
                    left = frames[j-1] if j else 0
                    for step in range(steps):
                        at = left + round((frames[j]-left)*(step+1)/steps)
                        t = (step+1)/steps
                        a, b = data['route'][j], data['route'][j+1]
                        x = round((a[0]+(b[0]-a[0])*t)*(520-20))+110
                        y = round((a[1]+(b[1]-a[1])*t)*(520-20))+400
                        filters.append(f"drawbox=x={x}:y={y}:w=14:h=14:color=0xaaf5cb:t=fill:enable='gte(n,{at})'")
                for j, pt in enumerate(data['route']):
                    at = 0 if j == 0 else data['reveal_frames'][j-1]
                    x = round(pt[0]*(520-20))+110
                    y = round(pt[1]*(520-20))+400
                    filters.append(f"drawbox=x={x-8}:y={y-8}:w=30:h=30:color=0xffeb94:t=fill:enable='gte(n,{at})'")
            elif recipe == 'kinetic_type':
                if reveal := data.get('type_reveal'):
                    draw('headline', 245, size('headline',54), ink)
                    for j,(phrase, at) in enumerate(zip(reveal['phrases'], reveal['reveal_frames'], strict=True)):
                        y = f"'{440+140*j}+42*pow(max(0,1-(n-{at})/6),3)'"
                        draw(f'phrase{j}', y, min(60,602//len(phrase)), ink, f":enable='gte(n,{at})'", value=phrase)
                    draw('detail', 1000, size('detail',40), secondary, f":enable='gte(n,{reveal['reveal_frames'][-1]})'")
                else:
                    draw('headline', "'500+90*pow(max(0,1-n/9),3)'", size('headline',70), ink)
                    draw('detail', "'660+70*pow(max(0,1-n/12),3)'", size('detail',56), secondary)
            elif recipe == 'card_sequence':
                draw('headline', 245, size('headline', 54), 'white')
                layout = data['layout']
                for j,(label, at) in enumerate(zip(data['cards'], data['reveal_frames'], strict=True)):
                    if layout == 'carousel':
                        end = (data['reveal_frames']+[count])[j+1]
                        show = f":enable='gte(n,{at})*lt(n,{end})'"
                        # Draw a stationary frame; animate its incoming text, not its readable hold.
                        x, y, w, h = 56, 477, 608, 250
                        text_x = f"'98+180*pow(max(0,1-(n-{at})/{CARD_SLIDE_FRAMES}),3)'"
                    else:
                        show = f":enable='gte(n,{at})'"
                        x, y, w, h = (56+28*j, 445+155*j, 550, 144) if layout == 'stack' else (56+312*j, 478, 296, 228)
                        text_x = x+24
                    filters.append(f'drawbox=x={x}:y={y}:w={w}:h={h}:color=0x263b4a:t=fill{show}')
                    draw(f'index{j}', y+35, 25, '0xaaf5cb', show, value=f'{j+1:02d}', x=x+24)
                    max_width = w-48 if layout != 'carousel' else w-230
                    draw(f'card{j}', y+83, min(42,max_width//len(label)), 'white', show, value=label, x=text_x)
            elif recipe == 'pose_swap':
                draw('headline', 245, size('headline', 54), 'white')
            elif recipe == 'shape_morph':
                draw('headline', 245, size('headline', 54), 'white')
                draw('detail', 815, size('detail', 46), '0xaaf5cb', f":enable='gte(n,{data['morph_end_frame']})'")
            elif recipe == 'diagram_data':
                draw('headline', 244, size('headline',54), 'white')
                for j,(label, at) in enumerate(zip(data['steps'], data['reveal_frames'], strict=True)):
                    y = 420 + 205*j
                    show = f":enable='gte(n,{at})'"
                    if j:
                        # Vertical connector and arrow point towards the newly revealed node.
                        span = data.get('connector_frames', 0)
                        for segment in range(6):
                            reveal = at-span+(segment+1)*span//6
                            filters.append(f"drawbox=x=356:y={y-80+segment*9}:w=7:h=9:color=0xaaf5cb:t=fill:enable='gte(n,{reveal})'")
                        draw(f'arrow{j}', y-42, 28, '0xaaf5cb', show, value='▼', x=347)
                    filters.append(f'drawbox=x=56:y={y}:w=608:h=125:color=0x263b4a:t=fill{show}')
                    draw(f'num{j}', y+45, 28, '0xaaf5cb', show, value=f'{j+1:02d}', x=86)
                    draw(f'step{j}', y+42, min(42, 480//len(label)), 'white', show, value=label, x=150)
            bg = '0x'+palette[0] if palette else ('0xfcf270' if recipe == 'kinetic_type' else '0x101820')
            source = ff+['-f','lavfi','-i',f'color={bg}:s={WIDTH}x{HEIGHT}:r={FPS}']
            geometry = '[0:v]'
            aux_inputs = 1
            if recipe == 'shape_morph':
                tile = work/'shape.rgb'
                with tile.open('wb') as stream:
                    for frame in range(count):
                        stream.write(shape_tile(data, frame))
                source += ['-f','rawvideo','-pixel_format','rgb24','-video_size',f'{SHAPE_SIZE}x{SHAPE_SIZE}', '-framerate',str(FPS),'-i',tile.name]
                geometry = '[0:v][1:v]overlay=260:500,'
                aux_inputs += 1
            elif recipe == 'pose_swap':
                from .motion_assets import load

                paths = [load(root, asset_id) for asset_id in data['poses']]
                for j, path in enumerate(paths):
                    source += ['-loop','1','-framerate',str(FPS),'-i',str(path)]
                    if j:
                        prep = ('[2:v]scale=520:520:force_original_aspect_ratio=decrease,'
                                'pad=520:520:(ow-iw)/2:(oh-ih)/2:color=0x1b2731,format=rgba')
                        geometry = f'{prep}[pose];[0:v][1:v]overlay=x=100:y=400'
                        geometry += f"[base];[base][pose]overlay=x=100:y=400:enable='gte(n,{data['at_frame']})',"
                        aux_inputs += 2
            elif recipe in ('image_reveal', 'map_route'):
                from .motion_assets import load

                asset = load(root, data['asset_id'])
                source += ['-loop','1','-framerate',str(FPS),'-i',str(asset)]
                aux_inputs += 1
                if recipe == 'map_route':
                    geometry = ('[1:v]scale=520:520:force_original_aspect_ratio=increase,crop=520:520,'
                                'format=yuv420p[asset];[0:v][asset]overlay=x=100:y=400,')
                else:
                    at, enter = data['at_frame'], 8
                    mode = data['mode']
                    prep = ('[1:v]scale=520:520:force_original_aspect_ratio=decrease,'
                            'pad=520:520:(ow-iw)/2:(oh-ih)/2:color=0x1b2731,format=rgba')
                    if mode == 'fade':
                        prep += f',fade=in:st={at/FPS:.4f}:d={enter/FPS:.4f}:alpha=1'
                    geometry = f'{prep}[asset];[0:v][asset]overlay=x=100:y=400'
                    if mode == 'slide':
                        geometry += f":y='400+120*pow(max(0,1-(n-{at})/8),3)'"
                    geometry += f":enable='gte(n,{at})'," if mode != 'fade' else ','
            program = geometry + ','.join(filters)
            if entrance := data.get('entrance'):
                source += ['-f','lavfi','-i',f'color=0x55717c:s={WIDTH}x{HEIGHT}:r={FPS}']
                sign = '-' if entrance['kind'] == 'wipe_left' else ''
                x = f"{sign}W*min(1,round(t*{FPS})/{entrance['duration_frames']})"
                program += f"[content];[content][{aux_inputs}:v]overlay=x='{x}':y=0"
            _run(source+['-filter_complex_threads','1','-filter_complex',program,'-frames:v',str(count),'-an','-c:v','libx264','-pix_fmt','yuv420p',f'{i}.mp4'], work)
            if recipe == 'shape_morph':
                tile.unlink()
        (work/'clips.txt').write_text(''.join(f"file '{i}.mp4'\n" for i in range(len(cuts))))
        _run(ff+['-f','concat','-safe','1','-i','clips.txt','-c','copy','-movflags','+faststart','preview.mp4'], work)
        _run(ff+['-xerror','-i','preview.mp4','-f','null','-'], work)
        if any(data.get('loop') for _,data in cuts):
            edges = subprocess.run(['ffmpeg','-v','error','-i','preview.mp4','-vf','select=eq(n\\,0)+eq(n\\,{})'.format(sum(n for n,_ in cuts)-1)+',scale=90:160',
                                    '-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],
                                   cwd=work, capture_output=True).stdout
            if len(edges) != 2*90*160*3 or edges[:90*160*3] != edges[90*160*3:]:
                raise ValueError('loop requested but the first and last frames do not match')
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
    from .project_skills import provenance, require_pack

    pack = require_pack(root)
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
    result = {**report,'human_review':True,'video':'final/motion.mp4','skill_pack':provenance(pack)}
    (target/'motion-delivery.json').write_text(json.dumps(result,indent=2))
    return result
