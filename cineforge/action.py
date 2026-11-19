"""Action-scene profile: impact rhythm, camera/speed contrast, continuity and safety checks."""
from __future__ import annotations

from typing import Any

DANGER = ('실제로 때', '목을 조', '계단에서 굴', '차에 매달', '불을 붙인', '진짜 칼', '실제 폭발')
SFX_WORDS = ('타격', '충돌', '부딪', '주먹', '발차기', '폭발', '총', '베', '찌르', '임팩트', '효과음', '소리')
BEATS: tuple[tuple[str, str, float, str, str, str, bool], ...] = (
    ('준비', 'setup', 1.6, '와이드샷', '핸드헬드', '느림', False),
    ('접근', 'approach', 0.9, '미디엄샷', '트래킹', '보통', False),
    ('타격', 'impact', 0.45, '클로즈업', '휩 팬', '빠름', True),
    ('반응', 'reaction', 1.1, '미디엄샷', '고정', '느림', False),
    ('재정렬', 'reset', 1.4, '투샷', '고정', '보통', False),
)


def is_action(*values: object) -> bool:
    return any('액션' in str(value) for value in values)


def action_cuts(length: float, characters: list[dict[str, Any]], purpose: str) -> list[dict[str, Any]]:
    """Fit the five-beat action rhythm into one scene without leaving slack."""
    rows: list[dict[str, Any]] = []
    budget = float(length)
    index = 0
    while budget > 0.05:
        label, role, want, shot, camera, speed, impact = BEATS[len(rows) % len(BEATS)]
        duration = min(want, budget)
        if budget - duration < 0.2:
            duration = budget
        attacker = characters[index % len(characters)]
        defender = characters[(index + 1) % len(characters)]
        rows.append({'no': len(rows) + 1, 'duration': round(duration, 2), 'shot': shot, 'camera': camera,
                     'speed': speed, 'impact': impact, 'beat': label,
                     'visual': f"{attacker['name']} → {defender['name']} {label}: {purpose}",
                     'sound': f"효과음: {label} 타격음과 저역" if impact else '앰비언스',
                     'dialogue': None, 'speaker': None,
                     'characters': [characters[0]['id'], characters[1]['id']] if len(characters) > 1 else [characters[0]['id']],
                     'state': {'end': {'changes': [f"{defender['name']} {label} 후 자세·균형 변화"]}} if impact else {}})
        budget = round(budget - duration, 2)
        index += 1
    return rows


def validate(ssots: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Action-only blockers; a quiet drama is not judged by these rules."""
    cuts = ssots['scene']['data']['cuts']
    cameras = {row['cut_id']: row for row in ssots['camera']['data']['cuts']}
    sounds = {cue.get('cut_id') for cue in ssots['audio']['data']['cues'] if cue['type'] == 'SFX'}
    issues: list[dict[str, Any]] = []
    seen_impact = False
    previous: dict[str, Any] | None = None
    for cut in cuts:
        if not cut.get('impact'):
            previous = cut
            continue
        seen_impact = True
        if previous is None or previous.get('scene_no') not in (None, cut.get('scene_no')):
            issues.append({'rule': 'AQ05', 'severity': 'warn', 'target': cut['cut_id'],
                           'message': '타격 앞에 준비 컷이 없음 — 접촉 전 거리·자세를 먼저 보여줘야 함'})
        previous = cut
        if float(cut['duration']) > 0.8:
            issues.append({'rule': 'AQ01', 'severity': 'error', 'target': cut['cut_id'],
                           'message': f"타격 컷 {cut['duration']}s — 0.8s 이하로 쪼개야 타격이 읽힘"})
        if not any(word in str(cut.get('sound') or '') for word in SFX_WORDS) or cut['cut_id'] not in sounds:
            issues.append({'rule': 'AQ06', 'severity': 'error', 'target': cut['cut_id'],
                           'message': '타격 컷에 타격 효과음 큐가 없음'})
        if cameras.get(cut['cut_id'], {}).get('crosses_axis'):
            issues.append({'rule': 'AQ04', 'severity': 'error', 'target': cut['cut_id'],
                           'message': '타격 중 축을 넘어 방향이 뒤집힘'})
        for person, hands in (cut['end_state'].get('holding') or {}).items():
            before = (cut['start_state'].get('holding') or {}).get(person, {})
            changed = [hand for hand, item in hands.items() if item and not before.get(hand)]
            if changed and not cut.get('state_changes'):
                issues.append({'rule': 'AQ03', 'severity': 'error', 'target': cut['cut_id'],
                               'message': f'{person} 소품이 이유 없이 생김 — 상태 변화를 기록해야 함'})
        if any(word in str(cut.get('visual') or '') for word in DANGER):
            issues.append({'rule': 'AQ07', 'severity': 'error', 'target': cut['cut_id'],
                           'message': '실제 위험 동작 지시 — 카메라·편집 표현으로 대체'})
    if not seen_impact:
        issues.append({'rule': 'AQ02', 'severity': 'warn', 'target': None,
                       'message': '액션 장면에 타격 컷이 없음 — 타격 비트를 확인'})
    return issues
