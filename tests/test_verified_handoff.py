import pytest
from cineforge.pipeline import Project
from cineforge.cli import main
from conftest import SAMPLE_REQUEST


def test_receipt_recovery_and_freshness(tmp_path, monkeypatch):
    p = Project.create(tmp_path, SAMPLE_REQUEST, 'mock', 'p')
    p.grant(accept_plan=True, accept_preproduction=True, execution=True)
    sid = 'S08_generation'
    p.run()
    f = p.root / 'take.mp4'
    f.write_bytes(b'first take')
    with monkeypatch.context() as patch:
        patch.setattr(p, 'set_stage', lambda *args, **kwargs: (_ for _ in ()).throw(InterruptedError()))
        with pytest.raises(InterruptedError):
            p.complete(sid, [str(f)])
    p = Project(p.root)
    p.run()
    assert p.progress()['stages'][sid]['status'] == 'done'
    f.write_bytes(b'another take')
    with pytest.raises(ValueError, match='receipt'):
        p.run()


def test_signed_pi_reply(tmp_path, monkeypatch):
    import json
    from cineforge.providers.host_agent import _HostIO
    from cineforge.providers.base import AgentInputRequired, ProviderError
    key = tmp_path/'key'
    key.write_bytes(bytes(range(32)))
    monkeypatch.setenv('CINEFORGE_HOST_KEY_FILE', str(key))
    io = _HostIO(tmp_path/'agent_io')
    payload = {'kind': 'decision', 'state': 'first'}
    with pytest.raises(AgentInputRequired) as ctx:
        io.exchange('tone', payload)
    req = ctx.value.request_path
    response = ctx.value.response_path
    body = {'answers': {'tone': {'choice': 'quiet'}}}
    response.write_text(json.dumps(body))
    with pytest.raises(ProviderError):
        io.exchange('tone', payload)
    from cineforge.host_sign import sign
    response.write_text(json.dumps(sign(json.loads(req.read_text()), body, key.read_bytes())))
    assert io.exchange('tone', payload) == body
    with pytest.raises(ProviderError):
        io.exchange('tone', dict(payload, state='changed'))
    monkeypatch.delenv('CINEFORGE_HOST_KEY_FILE')
    with pytest.raises(ProviderError):
        io.exchange('tone', payload)


def test_dialogue_override(tmp_path):
    args = ['new','한서윤 90초 숏드라마','--projects-dir',str(tmp_path),'--project-id','drama','--provider','mock','--non-interactive','--with-dialogue','--until','S03_plan']
    assert main(args) == 0
    c = Project(tmp_path/'drama').read('intake.json')['constraints']
    assert 'no_speech' not in c
    assert Project(tmp_path/'drama').read('intake.json')['detected_selection']['direction']['sound'] == 'dialogue_driven'
