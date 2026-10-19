from app.domains.site.diagrams import RUNNER_VERSION, generate_diagram


def test_diagram_generation_is_deterministic_and_source_bound() -> None:
    boundary = {"type": "Polygon", "coordinates": [[[77.59, 12.97], [77.60, 12.97], [77.60, 12.98], [77.59, 12.97]]]}
    analysis = {"site_revision_hash": "a" * 64, "source_context_hash": "b" * 64, "metrics": {"building_coverage_ratio": 0.25, "road_feature_count": 2, "road_length_m": 120.5}}
    first = generate_diagram("figure_ground", boundary, analysis)
    second = generate_diagram("figure_ground", boundary, analysis)
    assert first == second
    assert first["runner_version"] == RUNNER_VERSION
    assert first["source_context_hash"] == "b" * 64
    assert "Figure Ground" in first["svg"]
    assert "a" * 12 in first["svg"]


def test_movement_diagram_contains_deterministic_metrics() -> None:
    boundary = {"type": "Polygon", "coordinates": [[[77.59, 12.97], [77.60, 12.97], [77.60, 12.98], [77.59, 12.97]]]}
    analysis = {"site_revision_hash": "a" * 64, "source_context_hash": "b" * 64, "metrics": {"road_feature_count": 3, "road_length_m": 98.2}}
    svg = generate_diagram("movement", boundary, analysis)["svg"]
    assert "3" in svg
    assert "98.2 m" in svg
