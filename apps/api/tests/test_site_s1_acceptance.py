from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domains.site.analysis import analyze_site
from app.domains.site.diagrams import RUNNER_VERSION as DIAGRAM_RUNNER_VERSION, generate_diagram
from app.domains.site.validation import validate_boundary


BOUNDARY = {
    "type": "Polygon",
    "coordinates": [[[77.5900, 12.9700], [77.5910, 12.9700], [77.5910, 12.9710], [77.5900, 12.9710], [77.5900, 12.9700]]],
}


def revision():
    result = validate_boundary(BOUNDARY)
    return SimpleNamespace(
        id="revision-1",
        boundary_geojson=result.geojson,
        calculation_crs=result.calculation_crs,
        area_m2=result.area_m2,
        perimeter_m=result.perimeter_m,
        content_hash="a" * 64,
    )


def context_snapshot(identifier: str = "context-1"):
    return SimpleNamespace(
        id=identifier,
        provider="test-provider",
        dataset_version="2026.10",
        payload_json={
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"category": "road", "highway": "primary"}, "geometry": {"type": "LineString", "coordinates": [[77.589, 12.9705], [77.592, 12.9705]]}},
                {"type": "Feature", "properties": {"category": "building"}, "geometry": {"type": "Polygon", "coordinates": [[[77.5902, 12.9702], [77.5905, 12.9702], [77.5905, 12.9705], [77.5902, 12.9705], [77.5902, 12.9702]]]}},
            ],
        },
    )


def test_boundary_contract_is_metric_and_normalized() -> None:
    result = validate_boundary(BOUNDARY)
    assert result.geojson["type"] == "Polygon"
    assert result.calculation_crs.startswith("+proj=aeqd")
    assert result.area_m2 > 1
    assert result.perimeter_m > 0


def test_site_analysis_is_deterministic_and_unknown_without_unbound_environmental_sources() -> None:
    site = revision()
    snapshot = context_snapshot()
    first = analyze_site(site, [snapshot])
    second = analyze_site(site, [snapshot])
    assert first == second
    assert first["status"] == "SUPPORTED"
    assert first["metrics"]["road_feature_count"] == 1
    assert first["metrics"]["building_feature_count"] == 1
    assert first["environmental"]["climate"]["status"] == "UNKNOWN"
    assert first["environmental"]["terrain"]["status"] == "UNKNOWN"


def test_diagram_generation_is_source_bound_and_deterministic() -> None:
    site = revision()
    analysis = analyze_site(site, [context_snapshot()])
    first = generate_diagram("figure_ground", site.boundary_geojson, analysis)
    second = generate_diagram("figure_ground", site.boundary_geojson, analysis)
    assert first == second
    assert first["runner_version"] == DIAGRAM_RUNNER_VERSION
    assert first["source_context_hash"] == analysis["source_context_hash"]
    assert "Deterministic diagram" in first["svg"]


@pytest.mark.parametrize("diagram_type", ["figure_ground", "movement", "land_use", "green_water", "solar"])
def test_all_s1_diagram_types_produce_svg(diagram_type: str) -> None:
    site = revision()
    analysis = analyze_site(site, [context_snapshot()])
    diagram = generate_diagram(diagram_type, site.boundary_geojson, analysis)
    assert diagram["svg"].startswith('<svg ')
    assert diagram["diagram_type"] == diagram_type
