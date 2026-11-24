import pytest

from cineforge import provider_registry as reg


def test_registry_loads_and_covers_every_lane():
    rows = reg.load()
    assert len({r["id"] for r in rows}) == len(rows)
    for lane in reg.LANES:
        assert reg.by_lane(lane), lane


def test_research_providers_are_registered_with_real_endpoints():
    expect = {"runway": "https://mcp.runwayml.com/mcp", "pika": "https://mcp.pika.art/mcp",
              "kling": "https://kling.ai/mcp", "ludyte": "https://mcp.ludyte.com/mcp",
              "higgsfield": "https://mcp.higgsfield.ai/mcp", "suno": "https://api.suno.com/mcp",
              "fish-audio": "https://api.fish.audio/mcp", "heygen": "https://mcp.heygen.com/mcp/v1/"}
    for pid, url in expect.items():
        assert reg.get(pid)["url"] == url, pid
    assert len(reg.by_lane("video")) >= 30


def test_remote_entries_are_https_streamable_and_auth_is_known():
    for r in reg.load():
        assert r["auth"] in reg.AUTH and r["transport"] in reg.TRANSPORT and set(r["lanes"]) <= set(reg.LANES)
        if r["transport"] == "remote":
            assert r["url"].startswith("https://") and not r["url"].rstrip("/").endswith("/sse"), r["id"]
        if r["auth"] == "api_key":
            assert r.get("env_var"), r["id"]


def test_builtin_choices_exist_for_no_service_paths():
    assert reg.get("native-audio")["lanes"] == ["voice"]
    assert "music" in reg.get("none")["lanes"] and "sfx" in reg.get("none")["lanes"]
    assert reg.get("typecast")["transport"] == "cli"


def test_defaults_point_at_providers_serving_the_lane():
    for lane, pid in reg.defaults().items():
        assert lane in reg.get(pid)["lanes"]


def test_parse_flag_validates_lane_and_provider():
    assert reg.parse_flag("video=ludyte, voice=typecast") == {"video": "ludyte", "voice": "typecast"}
    with pytest.raises(ValueError, match="unknown_lane"):
        reg.parse_flag("color=ludyte")
    with pytest.raises(ValueError, match="provider_not_in_lane"):
        reg.parse_flag("music=runway")
    with pytest.raises(ValueError, match="unknown_provider"):
        reg.parse_flag("video=nope")


def test_availability_matches_installed_servers_by_name_or_url():
    rows = [{"agent": "codex", "name": "Ludyte", "url": "https://mcp.ludyte.com/mcp", "command": None},
            {"agent": "pi", "name": "my-runway", "url": "https://mcp.runwayml.com/mcp/", "command": None},
            {"agent": "pi", "name": "fish_audio", "url": None, "command": "node"}]
    av = reg.availability(rows)
    assert av["ludyte"] and av["runway"] and av["fish-audio"]
    assert not av["pika"]
    assert av["native-audio"] and av["none"]


def test_question_lists_options_per_lane_with_availability():
    q = reg.question(available={"ludyte": True})
    assert set(q["lanes"]) == set(reg.LANES)
    video = {o["id"]: o for o in q["lanes"]["video"]["options"]}
    assert video["ludyte"]["available"] is True and video["runway"]["available"] is False
    assert video["runway"]["auth"] == "oauth" and video["runway"]["docs"]
