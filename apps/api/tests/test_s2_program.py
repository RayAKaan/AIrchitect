from types import SimpleNamespace
from app.domains.program.service import build_program


def req(parameter, value, status="CONFIRMED"):
    return SimpleNamespace(id=parameter, parameter=parameter, normalized_value_json=value, status=status)


def test_program_has_stable_spaces_and_adjacencies():
    world = SimpleNamespace(model_hash="world-hash", model_json={"site": {"area": {"value": 2000}}})
    program = build_program([req("building_use", "office"), req("target_gfa", 3000), req("floor_count", 3)], world)
    assert program["schema_version"] == "s2-program-v1"
    assert program["target_gfa_m2"] == 3000
    ids = {space["id"] for space in program["spaces"]}
    assert ids
    assert all(edge["from"] in ids and edge["to"] in ids for edge in program["adjacencies"])


def test_program_does_not_hide_missing_gfa_when_site_inputs_are_insufficient():
    world = SimpleNamespace(model_hash="world-hash", model_json={"site": {}})
    try:
        build_program([req("building_use", "office")], world)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("Expected incomplete program input to block generation")
