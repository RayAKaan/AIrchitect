from types import SimpleNamespace

import pytest

from app.domains.envelope.service import build_envelope


def rule(value, unit, source="TEST_RULE", status="VERIFIED"):
    return SimpleNamespace(
        value=value,
        unit=unit,
        source=source,
        source_version="1",
        effective_date="2026-01-01",
        applicability="test",
        status=status,
        model_dump=lambda: {
            "value": value,
            "unit": unit,
            "source": source,
            "source_version": "1",
            "effective_date": "2026-01-01",
            "applicability": "test",
            "status": status,
        },
    )


def boundary():
    return {"type": "Polygon", "coordinates": [[[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001], [0, 0]]]}


def test_setback_reduces_buildable_area_and_preserves_unknowns():
    request = SimpleNamespace(setback_m=rule(5, "m"), max_coverage=None, far=None, max_height_m=None)
    result = build_envelope(boundary(), request)
    assert result["buildable_area_m2"] < result["site_area_m2"]
    assert result["unknowns"] == ["far", "max_coverage", "max_height_m"]
    assert result["environmental_context"]["unknowns"] == [
        "solar_exposure", "prevailing_wind", "climate_context"
    ]


def test_coverage_and_far_limit_max_gfa_deterministically():
    request = SimpleNamespace(
        setback_m=rule(0, "m"),
        max_coverage=rule(.5, "ratio"),
        far=rule(1.0, "ratio"),
        max_height_m=rule(20, "m"),
    )
    result = build_envelope(boundary(), request)
    assert result["max_gfa_m2"] == result["max_footprint_m2"]
    assert len(result["envelope_hash"]) == 64
    assert result["schema_version"] == "s2-envelope-v2"


def test_orientation_is_derived_from_metric_site_geometry():
    request = SimpleNamespace(
        setback_m=rule(0, "m"),
        max_coverage=None,
        far=None,
        max_height_m=None,
    )
    result = build_envelope(boundary(), request)
    orientation = result["site_orientation"]
    assert orientation["status"] == "DERIVED_FROM_SITE_GEOMETRY"
    assert 0 <= orientation["long_axis_degrees_from_north"] < 180


def test_unknown_status_does_not_turn_a_supplied_number_into_a_rule():
    request = SimpleNamespace(
        setback_m=rule(0, "m"),
        max_coverage=rule(.5, "ratio", status="UNKNOWN"),
        far=rule(1.5, "ratio", status="UNKNOWN"),
        max_height_m=rule(20, "m", status="UNKNOWN"),
    )
    result = build_envelope(boundary(), request)
    assert result["max_coverage"] is None
    assert result["far"] is None
    assert result["max_height_m"] is None
    assert set(result["unknowns"]) == {"max_coverage", "far", "max_height_m"}


@pytest.mark.parametrize(
    ("name", "value", "unit"),
    [
        ("setback_m", float("nan"), "m"),
        ("max_coverage", 1.2, "ratio"),
        ("far", -0.1, "ratio"),
        ("max_height_m", float("inf"), "m"),
    ],
)
def test_invalid_planning_values_fail_closed(name, value, unit):
    request = SimpleNamespace(
        setback_m=rule(0, "m"),
        max_coverage=None,
        far=None,
        max_height_m=None,
    )
    setattr(request, name, rule(value, unit))
    with pytest.raises(Exception) as exc_info:
        build_envelope(boundary(), request)
    assert getattr(exc_info.value, "status_code", None) == 422
