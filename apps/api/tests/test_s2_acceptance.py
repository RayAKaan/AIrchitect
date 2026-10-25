from types import SimpleNamespace

from app.domains.design.strategies import STRATEGIES
from app.domains.envelope.service import build_envelope
from app.domains.program.service import build_program
from app.domains.requirements.service import analyze_brief


def _rule(value, unit):
    return SimpleNamespace(value=value, unit=unit, source="TEST", source_version="1", effective_date="2026-01-01",
        applicability="test", status="VERIFIED", model_dump=lambda: {"value": value, "unit": unit, "source": "TEST"})


def _req(parameter, value):
    return SimpleNamespace(id=parameter, parameter=parameter, normalized_value_json=value, status="CONFIRMED")


def test_s2_brief_requirements_program_envelope_concepts_are_traceable():
    brief = "A 3 floor office building with 3000 sqm GFA on a 2000 sqm site."
    requirements, missing, issues = analyze_brief(brief)
    assert requirements
    assert not issues
    assert "budget or cost constraint" in missing

    world = SimpleNamespace(model_hash="world-hash", model_json={"site": {"area": {"value": 2000}}})
    program = build_program([_req("building_use", "office"), _req("target_gfa", 3000), _req("floor_count", 3)], world)
    assert program["provenance"]["world_model_hash"] == "world-hash"
    assert all(space["target_area_m2"] > 0 for space in program["spaces"])

    boundary = {"type":"Polygon","coordinates":[[[0,0],[0.001,0],[0.001,0.001],[0,0.001],[0,0]]]} 
    envelope = build_envelope(boundary, SimpleNamespace(setback_m=_rule(5,"m"), max_coverage=_rule(.6,"ratio"),
        far=_rule(1.5,"ratio"), max_height_m=_rule(20,"m")))
    assert envelope["unknowns"] == []
    assert len(envelope["envelope_hash"]) == 64
    assert [s.id for s in STRATEGIES] == ["balanced", "compact", "low_rise"]


def test_s2_missing_planning_data_is_explicit_not_fabricated():
    boundary = {"type":"Polygon","coordinates":[[[0,0],[0.001,0],[0.001,0.001],[0,0.001],[0,0]]]} 
    result = build_envelope(boundary, SimpleNamespace(setback_m=_rule(0,"m"), max_coverage=None, far=None, max_height_m=None))
    assert set(result["unknowns"]) == {"far", "max_coverage", "max_height_m"}
