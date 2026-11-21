from cineforge.audio_design import cues_from_plan
from cineforge.planner import build_payload, mock_plan
from cineforge.action import action_cuts, validate


def _payload(profile_genres=('액션',), seconds=30):
    concept = {'format': '숏드라마', 'genres': list(profile_genres), 'subgenres': [], 'duration_s': seconds,
               'title_line': 't', 'subtitle': 's', 'chain': '', 'emotion_arc': '', 'aspect': '9:16'}
    selection = {'free_text': {'lead_character': '서윤'}, 'constraints': [], 'direction': {}, 'aspect': '9:16'}
    labels = {'genre': list(profile_genres), 'setting': '실내 공간'}
    return build_payload(selection, {'concept': concept}, {'detected_selection': {}}, labels, 3.0)


def test_action_cuts_use_impact_rhythm():
    rows = action_cuts(12.0, [{'id': 'CH01', 'name': '서윤'}, {'id': 'CH02', 'name': '상대'}], '복도 충돌')
    impact = [row for row in rows if row['impact']]
    assert impact and all(row['duration'] <= 0.7 for row in impact)
    assert min(row['duration'] for row in rows if not row['impact']) >= 0.8
    assert any(row['camera'] != '고정' for row in rows)
    assert {'빠름', '보통', '느림'} <= {row['speed'] for row in rows}
    assert all(row['state']['end']['changes'] for row in impact)
    assert abs(sum(row['duration'] for row in rows) - 12.0) < 0.2


def test_dialogue_project_has_no_action_profile():
    plan = mock_plan(_payload(('코미디',), 30))
    assert plan['meta'].get('profile') != 'action'
    assert not any(row.get('impact') for scene in plan['scenes'] for row in scene['cuts'])


def test_action_plan_carries_profile_and_rhythm():
    plan = mock_plan(_payload(('액션',), 30))
    assert plan['meta']['profile'] == 'action'
    cuts = [cut for scene in plan['scenes'] for cut in scene['cuts']]
    assert any(cut['impact'] for cut in cuts)
    assert any(cut['camera'] != '고정' for cut in cuts)
    assert abs(sum(cut['duration'] for cut in cuts) - 30) < 0.6


def test_impact_window_ducks_music_and_adds_hit_sfx():
    plan = {'scenes': [{'no': 1, 'title': '충돌', 'start': 0, 'end': 8, 'cuts': []}],
            'production_spec': {'bgm': '저역 타악'}}
    cuts = [{'cut_id': 'S01C01', 'start': 2.0, 'end': 2.5, 'sound': '타격음', 'impact': True, 'dialogue': None}]
    rows = cues_from_plan(cuts, plan, False)
    window = (2.0, 2.5)
    music = [row for row in rows if row['type'] in ('BGM', 'OST')]
    assert all(not (row['tc_in'] < window[1] and window[0] < row['tc_out']) for row in music)
    assert any(row['type'] == 'SFX' and row['cut_id'] == 'S01C01' for row in rows)


def _ssots(cuts, actions=()):
    return {
        'scene': {'data': {'cuts': cuts}},
        'camera': {'data': {'cuts': [{'cut_id': c['cut_id'], 'axis_side': c.get('axis', 'A'), 'crosses_axis': c.get('crosses_axis', False)}
                                     for c in cuts]}},
        'motion': {'data': {'cuts': [{'cut_id': c['cut_id'], 'speed': c.get('speed', '보통')} for c in cuts]}},
        'audio': {'data': {'cues': [{'type': 'SFX', 'cut_id': c.get('hit_cue')} for c in cuts if c.get('hit_cue')]}},
        'character': {'data': {'characters': [{'id': 'CH01', 'name': '서윤'}]}},
    }


def _cut(cut_id, duration, **extra):
    row = {'cut_id': cut_id, 'duration': duration, 'characters': ['CH01'], 'impact': False, 'sound': '',
           'start_state': {'positions': {'CH01': 'left'}, 'holding': {'CH01': {'left': None, 'right': None}}},
           'end_state': {'positions': {'CH01': 'left'}, 'holding': {'CH01': {'left': None, 'right': None}}},
           'visual': '동작', 'dialogue': None, 'state_changes': []}
    row.update(extra)
    return row


def test_action_qa_finds_real_defects():
    impact = _cut('S01C01', 1.4, impact=True, sound='타격음', hit_cue='S01C01')
    silent_hit = _cut('S01C02', 0.4, impact=True, sound='앰비언스', hit_cue=None, state_changes=['자세'])
    teleport = _cut('S01C03', 0.5, impact=True, sound='타격음', hit_cue='S01C03', crosses_axis=True)
    teleport['end_state'] = {'positions': {'CH01': 'left'}, 'holding': {'CH01': {'left': '칼', 'right': None}}}
    danger = _cut('S01C04', 0.5, impact=True, sound='타격음', hit_cue='S01C04', state_changes=['자세'],
                  visual='배우가 실제로 계단에서 굴러 떨어진다')
    issues = validate(_ssots([impact, silent_hit, teleport, danger]))
    rules = {issue['rule'] for issue in issues}
    assert {'AQ01', 'AQ03', 'AQ04', 'AQ06', 'AQ07'} <= rules
    first_hit = validate(_ssots([_cut('S01C01', 0.4, impact=True, sound='타격음', hit_cue='S01C01')]))
    assert 'AQ05' in {issue['rule'] for issue in first_hit}


def test_action_qa_ignores_a_clean_sequence():
    setup = _cut('S01C01', 1.6, sound='앰비언스')
    hit = _cut('S01C02', 0.4, impact=True, sound='타격음', hit_cue='S01C02', state_changes=['자세'])
    assert validate(_ssots([setup, hit])) == []
