from cineforge.data_loader import load

USER_COUNTS = {"culture_style": 22, "romance_concept": 24, "story_nature": 23, "narrative": 12}


def test_user_lists_complete(tax):
    for axis, n in USER_COUNTS.items():
        user_items = [i for i in tax.items(axis) if i.data.get("source", "user") == "user"]
        assert len(user_items) == n, axis


def test_world_has_24_user_concepts(tax):
    assert len(tax.items("world", "fantasy_world")) == 24


def test_format_has_12_categories(tax):
    assert len(tax.axis("format")["groups"]) == 12


def test_durations_and_axes(tax):
    assert [i.id for i in tax.items("duration")] == ["s15", "s30", "s60", "s90"]
    assert len(tax.axis("direction")["groups"]) == 8
    assert {"texture", "viewpoint", "camera", "expression", "edit_rhythm", "color_light", "reality", "sound"} == {g["id"] for g in tax.axis("direction")["groups"]}


def test_ids_unique_per_axis(tax):
    for axis in tax.order():
        if axis == "direction":
            for g in tax.axis(axis)["groups"]:
                ids = [i.id for i in tax.items(axis, g["id"])]
                assert len(ids) == len(set(ids))
        else:
            ids = [i.id for i in tax.items(axis)]
            assert len(ids) == len(set(ids)), axis


def test_resolve_by_korean_label(tax):
    assert tax.resolve("narrative", "결말 선공개형").id == "ending_first"
    assert tax.resolve("culture_style", "K-드라마").id
    assert tax.resolve("direction", "시네마틱", "texture").id == "cinematic"


def test_presets_reference_valid_items(tax):
    from cineforge.selection import merge, new_selection, validate
    assert {"concept_a_zombie", "concept_b_stickman", "concept_c_first_love"} <= set(tax.presets)
    for pid, preset in tax.presets.items():
        sel = merge(new_selection(), preset["selection"], "preset")
        errors = [e for e in validate(sel, tax) if "필수" not in e]
        assert not errors, (pid, errors)


def test_rules_reference_valid_items(tax):
    rules = load("rules.yaml")
    for rule in rules["compatibility"]:
        for key, val in rule["when"].items():
            vals = val if isinstance(val, list) else [val]
            if key.startswith("direction."):
                group = key.split(".", 1)[1]
                assert all(tax.has("direction", v, group) for v in vals), rule["id"]
            elif key in tax.axes:
                assert all(tax.has(key, v) for v in vals), (rule["id"], key, vals)
    assert len(rules["direction_rules"]) >= 14
