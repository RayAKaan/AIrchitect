from types import SimpleNamespace

import pytest

from app.domains.program.service import build_program


def req(parameter, value, status="CONFIRMED"):
    return SimpleNamespace(id=parameter, parameter=parameter, normalized_value_json=value, status=status)


def world(model=None):
    return SimpleNamespace(
        model_hash="world-hash",
        model_json=model or {"site": {"area": {"value": 2000}, "width": {"value": 40}, "depth": {"value": 50}}},
    )


def test_program_has_stable_spaces_and_adjacencies():
    program = build_program(
        [req("building_use", "office"), req("target_gfa", 3000), req("floor_count", 3)],
        world(),
    )
    assert program["schema_version"] == "s2-program-v2"
    assert program["target_gfa_m2"] == 3000
    ids = {space["id"] for space in program["spaces"]}
    assert ids
    assert all(edge["from"] in ids and edge["to"] in ids for edge in program["adjacencies"])
    assert program["area_reconciliation"]["reconciled"] is True
    assert program["area_reconciliation"]["allocated_space_area_m2"] == 3000


def test_program_does_not_hide_missing_gfa_when_site_inputs_are_insufficient():
    with pytest.raises(Exception) as exc_info:
        build_program([req("building_use", "office")], world({"site": {}}))
    assert getattr(exc_info.value, "status_code", None) == 409


def test_missing_building_use_is_an_explicit_assumption_not_a_fact():
    program = build_program([req("target_gfa", 1200)], world())
    assumption = next(item for item in program["assumptions"] if item["parameter"] == "building_use")
    assert assumption["value"] == "office"
    assert "must be reviewed" in assumption["reason"]


def test_commercial_retail_alias_resolves_to_retail_program():
    program = build_program(
        [req("building_use", "commercial_retail"), req("target_gfa", 1200)],
        world(),
    )
    assert program["use"] == "retail"
    assert any(space["space_type"] == "sales_floor" for space in program["spaces"])


def test_each_supported_building_use_has_valid_relationships():
    for use in ("office", "retail", "restaurant", "residential"):
        program = build_program(
            [req("building_use", use), req("target_gfa", 1000)],
            world(),
        )
        ids = {space["id"] for space in program["spaces"]}
        assert program["adjacencies"]
        assert all(edge["from"] in ids and edge["to"] in ids for edge in program["adjacencies"])


def test_site_context_never_fabricates_orientation_or_frontage():
    program = build_program(
        [req("building_use", "office"), req("target_gfa", 1000)],
        world(),
    )
    assert program["site_context"]["orientation_status"] == "UNKNOWN"
    assert program["site_context"]["access_frontage_status"] == "UNKNOWN"
    assert "site_orientation" in program["unknowns"]
    assert "site_access_frontage" in program["unknowns"]
