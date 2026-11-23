import pytest

from cineforge import goal_contract as gc


def kind(text, forced=None):
    r = gc.resolve(text, forced)
    return r['goal']['kind'] if r['status'] == 'resolved' else r['reason']


def test_board_only_negation():
    assert kind('15초 9:16 광고 영상은 만들지 말고 스토리보드만') == 'text_storyboard'
    assert kind('15초 광고 스토리보드만 만들어줘') == 'text_storyboard'


def test_board_then_mp4_is_delivery():
    assert kind('보드부터 만들고 최종 MP4까지 납품해줘') == 'delivery_mp4'


def test_ambiguous_and_unsupported_not_guessed():
    assert kind('광고 준비해줘') == 'ambiguous_deliverable'
    assert kind('이미지 스토리보드 만들어줘') == 'unsupported_scope'
    assert kind('') == 'empty_request'


def test_constraints_captured_not_dropped():
    g = gc.resolve('15초 9:16 스토리보드만', None)['goal']
    assert g['constraints'] == {'duration_s': 15.0, 'aspect': '9:16'}


def test_validation_rejects_bad_values():
    base = {'version': 1, 'revision': 1, 'kind': 'text_storyboard', 'request': 'x', 'constraints': {}}
    gc.validate(base)
    for bad in ({**base, 'version': 2}, {**base, 'kind': 'x'}, {**base, 'constraints': {'duration_s': -1}},
                {**base, 'constraints': {'aspect': '7:3'}}, {**base, 'revision': 0}):
        with pytest.raises(gc.GoalError):
            gc.validate(bad)


def test_revision_bumps_only_on_change(tmp_path):
    g = gc.resolve('15초 스토리보드만', None)['goal']
    assert gc.write(tmp_path, g)['revision'] == 1
    assert gc.write(tmp_path, g)['revision'] == 1
    assert gc.write(tmp_path, {**g, 'kind': 'delivery_mp4'})['revision'] == 2
