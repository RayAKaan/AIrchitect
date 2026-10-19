"""Validate the versioned S0.6 benchmark corpus."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "benchmarks"

EXPECTED = {
    "briefs": (20, {"id", "type", "project", "site_area_m2", "hard", "guidance", "unknowns", "expected"}),
    "sites": (10, {"id", "name", "context", "crs", "projected_crs", "boundary", "expected"}),
    "concepts": (10, {"id", "brief_id", "site_id", "typologies", "required_metrics", "expectation"}),
    "layouts": (10, {"id", "concept_id", "spaces", "relationships", "invariants"}),
    "regeneration": (10, {"id", "trigger", "source", "expected_stale", "expected_current", "invariant"}),
    "boards": (10, {"id", "source", "size", "items", "required", "stale_behavior"}),
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError(f"invalid JSON: {path}: {exc}") from exc


def assert_string_set(value: Any, field: str, case_id: str) -> None:
    assert isinstance(value, list) and value, f"{case_id}: {field} must be a non-empty list"
    assert all(isinstance(item, str) and item.strip() for item in value), f"{case_id}: {field} contains non-string values"


def validate_case(category: str, case: dict[str, Any], fields: set[str]) -> None:
    assert fields.issubset(case), f"{category}/{case.get('id', '<unknown>')}: missing fields {sorted(fields - case.keys())}"
    assert isinstance(case["id"], str) and case["id"].startswith(category.upper()[:-1] + "-")
    assert_string_set(case["hard"], "hard", case["id"]) if category == "briefs" else None
    if category == "briefs":
        assert isinstance(case["site_area_m2"], (int, float)) and case["site_area_m2"] > 0
        assert isinstance(case["expected"], dict) and case["expected"].get("requirements_min", 0) >= 4
        assert case["expected"].get("fabricated_rules") == 0
        assert_string_set(case["unknowns"], "unknowns", case["id"])
    elif category == "sites":
        assert case["crs"] == "EPSG:4326"
        assert case["projected_crs"] == "LOCAL_METRIC"
        boundary = case["boundary"]
        assert isinstance(boundary, list) and len(boundary) >= 4
        assert all(isinstance(point, list) and len(point) == 2 for point in boundary)
        assert isinstance(case["expected"], dict)
    elif category == "concepts":
        assert len(case["typologies"]) >= 3
        assert len(case["required_metrics"]) >= 3
    elif category == "layouts":
        assert_string_set(case["spaces"], "spaces", case["id"])
        assert isinstance(case["relationships"], list)
        assert_string_set(case["invariants"], "invariants", case["id"])
    elif category == "regeneration":
        assert isinstance(case["expected_stale"], list)
        assert isinstance(case["expected_current"], list)
        assert isinstance(case["invariant"], str) and case["invariant"]
    elif category == "boards":
        assert_string_set(case["items"], "items", case["id"])
        assert_string_set(case["required"], "required", case["id"])
        assert "stale" in case["stale_behavior"].lower()


def main() -> int:
    manifest = load_json(BASE / "manifest.json")
    assert manifest["schema_version"] == "1.0"
    assert manifest["corpus_version"]
    assert set(manifest["categories"]) == set(EXPECTED)

    all_ids: set[str] = set()
    for category, (expected_count, fields) in EXPECTED.items():
        path = BASE / category / "cases.json"
        cases = load_json(path)
        assert isinstance(cases, list), f"{category}: cases.json must contain an array"
        assert len(cases) == expected_count, f"{category}: expected {expected_count}, found {len(cases)}"
        ids = [case.get("id") for case in cases]
        assert all(isinstance(case, dict) for case in cases), f"{category}: every case must be an object"
        assert len(ids) == len(set(ids)), f"{category}: duplicate case IDs"
        assert not all_ids.intersection(ids), f"duplicate IDs across categories: {set(ids) & all_ids}"
        all_ids.update(ids)
        for case in cases:
            validate_case(category, case, fields)

    manifest_ids = {case_id for ids in manifest["cases"].values() for case_id in ids}
    assert manifest_ids == all_ids, "manifest case index does not match corpus"

    concept_ids = {case["id"] for case in load_json(BASE / "concepts/cases.json")}
    brief_ids = {case["id"] for case in load_json(BASE / "briefs/cases.json")}
    site_ids = {case["id"] for case in load_json(BASE / "sites/cases.json")}
    layout_cases = load_json(BASE / "layouts/cases.json")
    for case in load_json(BASE / "concepts/cases.json"):
        assert case["brief_id"] in brief_ids and case["site_id"] in site_ids
    for case in layout_cases:
        assert case["concept_id"] in concept_ids
    for case in load_json(BASE / "boards/cases.json"):
        assert case["source"] in concept_ids

    print(f"Benchmark corpus valid: {len(all_ids)} cases across {len(EXPECTED)} categories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
