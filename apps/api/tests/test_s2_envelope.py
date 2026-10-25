from types import SimpleNamespace
from app.domains.envelope.service import build_envelope


def rule(value, unit, source="TEST_RULE"):
    return SimpleNamespace(value=value, unit=unit, source=source, source_version="1", effective_date="2026-01-01", applicability="test", status="VERIFIED", model_dump=lambda: {"value": value, "unit": unit, "source": source})


def test_setback_reduces_buildable_area_and_preserves_unknowns():
    boundary = {"type":"Polygon","coordinates":[[[0,0],[0.001,0],[0.001,0.001],[0,0.001],[0,0]]]} 
    request = SimpleNamespace(setback_m=rule(5,"m","planning"), max_coverage=None, far=None, max_height_m=None)
    result = build_envelope(boundary, request)
    assert result["buildable_area_m2"] < result["site_area_m2"]
    assert result["unknowns"] == ["far", "max_coverage", "max_height_m"]


def test_coverage_and_far_limit_max_gfa_deterministically():
    boundary = {"type":"Polygon","coordinates":[[[0,0],[0.001,0],[0.001,0.001],[0,0.001],[0,0]]]} 
    request = SimpleNamespace(setback_m=rule(0,"m"), max_coverage=rule(.5,"ratio"), far=rule(1.0,"ratio"), max_height_m=rule(20,"m"))
    result = build_envelope(boundary, request)
    assert result["max_gfa_m2"] == result["max_footprint_m2"]
    assert len(result["envelope_hash"]) == 64
