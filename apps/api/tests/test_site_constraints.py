from types import SimpleNamespace

from app.domains.site.constraints import RUNNER_VERSION, detect_constraints


def test_constraints_are_deterministic_and_source_bound() -> None:
    revision = SimpleNamespace(id="rev-1", content_hash="a" * 64)
    analysis = {"source_context_hash": "b" * 64, "metrics": {"building_coverage_ratio": 0.8, "water_area_m2": 12.5}, "warnings": []}
    first = detect_constraints(revision, analysis)
    second = detect_constraints(revision, analysis)
    assert first == second
    assert RUNNER_VERSION == first[0]["runner_version"]
    assert {item["type"] for item in first} == {"HIGH_EXISTING_COVERAGE", "WATER_CONTEXT"}
    assert all(item["site_revision_hash"] == revision.content_hash for item in first)
    assert all(item["source_context_hash"] == analysis["source_context_hash"] for item in first)
