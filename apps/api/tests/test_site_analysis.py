from types import SimpleNamespace

from app.domains.site.analysis import RUNNER_VERSION, analyze_site


def test_site_analysis_is_deterministic_and_source_bound() -> None:
    revision = SimpleNamespace(
        id="rev-1",
        content_hash="a" * 64,
        area_m2=10000.0,
        perimeter_m=400.0,
        calculation_crs="+proj=aeqd +lat_0=12.97 +lon_0=77.59 +datum=WGS84 +units=m +no_defs",
        boundary_geojson={"type": "Polygon", "coordinates": [[[77.59, 12.97], [77.60, 12.97], [77.60, 12.98], [77.59, 12.97]]]},
    )
    snapshot = SimpleNamespace(
        id="ctx-1", provider="fixture", dataset_version="1", payload_json={"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"layer": "building", "land_use": "retail"}, "geometry": {"type": "Polygon", "coordinates": [[[77.5901, 12.9701], [77.5902, 12.9701], [77.5902, 12.9702], [77.5901, 12.9701]]]}},
            {"type": "Feature", "properties": {"layer": "road"}, "geometry": {"type": "LineString", "coordinates": [[77.589, 12.971], [77.601, 12.971]]}},
        ]}
    )
    first = analyze_site(revision, [snapshot])
    second = analyze_site(revision, [snapshot])
    assert first == second
    assert first["runner_version"] == RUNNER_VERSION
    assert first["status"] == "SUPPORTED"
    assert first["source_context_hash"]
    assert first["metrics"]["building_feature_count"] == 1
    assert first["metrics"]["road_feature_count"] == 1
    assert first["metrics"]["land_use_counts"] == {"retail": 1}
