"""Sound design derived from the plan, shared by script, board and cue sheet."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CueType = Literal['OST', 'BGM', 'AMBIENCE', 'SFX', 'DIALOGUE']
LEVELS = {'OST': '-14 LUFS', 'BGM': '-20 dB under', 'AMBIENCE': '-28 LUFS', 'SFX': '-12 LUFS', 'DIALOGUE': '-6 LUFS'}
SFX_WORDS = ('효과음', '소리', '스크래치', '타격', '낙하음', 'SFX', '임팩트', '발소리', '문', '유리', '숨', '바람', '벨', '전화', '타이핑')


@dataclass(frozen=True, slots=True)
class Design:
    scene_no: int
    ost: str | None
    bgm: bool
    ambience: str
    sfx: tuple[str, ...]


def design(plan: dict[str, Any], *, silent: bool) -> tuple[Design, ...]:
    """One decision per scene: which layer carries the moment."""
    scenes = plan['scenes']
    rows = []
    for index, scene in enumerate(scenes):
        opening = index == 0
        closing = index == len(scenes) - 1 and len(scenes) > 1
        ost = 'opening' if opening else 'ending' if closing else None
        sounds = tuple(str(cut.get('sound') or '') for cut in scene['cuts'] if cut.get('sound'))
        sfx = tuple(text for text in sounds if any(word in text for word in SFX_WORDS))
        rows.append(Design(int(scene['no']), ost, not (opening and closing), str(scene.get('location') or '공간'), sfx))
    return tuple(rows)


def cue_rows(plan: dict[str, Any], silent: bool, cuts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Scheduled cues; OST replaces BGM on the same span instead of stacking."""
    rows: list[dict[str, Any]] = []
    for row, scene in zip(design(plan, silent=silent), plan['scenes'], strict=True):
        start, end = float(scene['start']), float(scene['end'])
        if row.ost:
            span = min(12.0, max(4.0, (end - start) / 2))
            at = start if row.ost == 'opening' else max(start, end - span)
            rows.append({'type': 'OST', 'tc_in': at, 'tc_out': min(end, at + span), 'cut_id': None,
                         'description': f"주제가 {row.ost} — {scene.get('title', '')}", 'vocal': not silent,
                         'role': 'main theme'})
            if at > start:
                rows.append({'type': 'BGM', 'tc_in': start, 'tc_out': at, 'cut_id': None,
                             'description': f"씬{scene['no']} 도입 언더스코어", 'vocal': False, 'role': 'underscore'})
            if at + span < end:
                rows.append({'type': 'BGM', 'tc_in': at + span, 'tc_out': end, 'cut_id': None,
                             'description': f"씬{scene['no']} 마무리 언더스코어", 'vocal': False, 'role': 'underscore'})
            continue
        rows.append({'type': 'BGM', 'tc_in': start, 'tc_out': end, 'cut_id': None,
                     'description': f"씬{scene['no']} {scene.get('title', '')} — {plan['production_spec'].get('bgm', '')}",
                     'vocal': False, 'role': 'underscore'})
    for row, scene in zip(design(plan, silent=silent), plan['scenes'], strict=True):
        rows.append({'type': 'AMBIENCE', 'tc_in': float(scene['start']), 'tc_out': float(scene['end']), 'cut_id': None,
                     'description': f"{row.ambience} 공간음", 'vocal': False, 'role': 'room tone'})
    for cut in cuts or []:
        sound = str(cut.get('sound') or '')
        if any(word in sound for word in SFX_WORDS):
            rows.append({'type': 'SFX', 'tc_in': float(cut['start']), 'tc_out': float(cut['end']),
                         'cut_id': cut['cut_id'], 'description': sound, 'vocal': False, 'role': 'spot effect'})
        if cut.get('dialogue') and not silent:
            rows.append({'type': 'DIALOGUE', 'tc_in': float(cut['start']), 'tc_out': float(cut['end']),
                         'cut_id': cut['cut_id'], 'description': f"{cut.get('speaker')}: {cut['dialogue']}",
                         'vocal': True, 'role': 'dialogue'})
    rows = _duck_music(rows, cuts or [])
    rows.sort(key=lambda cue: (float(cue['tc_in']), cue['type']))
    return rows


def _duck_music(rows: list[dict[str, Any]], cuts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop music out of an impact window; a hit is heard, not scored over."""
    windows = [(float(cut['start']), float(cut['end'])) for cut in cuts if cut.get('impact')]
    if not windows:
        return rows
    kept: list[dict[str, Any]] = []
    for row in rows:
        if row['type'] not in ('BGM', 'OST'):
            kept.append(row)
            continue
        start, end = float(row['tc_in']), float(row['tc_out'])
        for hit_in, hit_out in windows:
            if end <= hit_in or start >= hit_out:
                continue
            if start < hit_in:
                kept.append(dict(row, tc_out=hit_in))
            if end > hit_out:
                kept.append(dict(row, tc_in=hit_out))
            break
        else:
            kept.append(row)
    return kept


def cues_from_plan(cuts: list[dict[str, Any]], plan: dict[str, Any], silent: bool) -> list[dict[str, Any]]:
    """Public entry used by the audio SSOT; schedules and numbers the cues."""
    from .local_motion import compile_plan, has_local_motion

    # Silence for a local structured motion lane is different from no dialogue.
    if has_local_motion(plan):
        compile_plan(plan)
        return []
    numbered = []
    for index, row in enumerate(cue_rows(plan, silent, cuts), start=1):
        numbered.append({'cue_id': f'Q{index:03d}', 'type': row['type'], 'tc_in': round(float(row['tc_in']), 2),
                         'tc_out': round(float(row['tc_out']), 2), 'cut_id': row['cut_id'],
                         'description': row['description'], 'level': LEVELS[row['type']],
                         'source': 'generate' if row['type'] != 'AMBIENCE' else 'generate-loop',
                         'license': 'original-to-generate', 'vocal': row['vocal'], 'role': row['role'], 'notes': ''})
    return numbered
