from __future__ import annotations

import hashlib
import json

from app.domains.spatial_layout.topology import SpatialTopologyError, build_spatial_topology


def _seal(layout: dict) -> dict:
    payload = dict(layout)
    payload["layout_hash"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return payload


def _space(
    space_id: str,
    program_space_id: str,
    space_type: str,
    category: str,
    level: int,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> dict:
    return {
        "id": space_id,
        "program_space_id": program_space_id,
        "space_type": space_type,
        "category": category,
        "level_number": level,
        "area_m2": (x2 - x1) * (y2 - y1),
        "boundary": [
            [x1, y1, 0.0],
            [x2, y1, 0.0],
            [x2, y2, 0.0],
            [x1, y2, 0.0],
            [x1, y1, 0.0],
        ],
    }


def _layout() -> dict:
    return _seal({
        "schema_version": "phase3-spatial-layout-v1",
        "project_id": "project-1",
        "project_version_id": "version-1",
        "world_model_hash": "a" * 64,
        "selected_alternative_id": "alternative-1",
        "program_hash": "b" * 64,
        "envelope_hash": "c" * 64,
        "spaces": [
            _space("core-l1", "core", "core", "service", 1, 0, 0, 2, 10),
            _space("room-a", "reception", "reception", "public", 1, 2, 0, 7, 10),
            _space("corridor-l1", "circulation", "circulation", "circulation", 1, 7, 0, 9, 10),
            _space("room-b", "open_work", "open_work", "primary", 1, 9, 0, 14, 10),
            _space("core-l2", "core", "core", "service", 2, 0, 0, 2, 10),
            _space("room-c", "bedroom", "bedroom", "private", 2, 2, 0, 7, 10),
            _space("room-d", "bathroom", "bathroom", "service", 2, 10, 0, 12, 10),
        ],
        "adjacencies": [
            {
                "from_space_id": "room-a",
                "to_space_id": "room-b",
                "relationship": "direct",
                "required": True,
                "status": "UNSATISFIED",
            }
        ],
        "source_lineage": {
            "world_model_hash": "a" * 64,
            "program_hash": "b" * 64,
            "envelope_hash": "c" * 64,
            "alternative_id": "alternative-1",
            "envelope_source_lineage": {"site_revision_id": "site-revision-1"},
        },
    })


def test_topology_derives_shared_boundaries_and_explicit_circulation_review():
    topology = build_spatial_topology(_layout())

    assert len(topology["nodes"]) == 7
    assert len(topology["edges"]) == 4
    assert topology["boundary_adjacency_components"][0]["component_count"] == 1
    assert topology["boundary_adjacency_components"][1]["component_count"] == 2
    assert topology["circulation_network"]["status"] == "CANDIDATE_ONLY"
    assert topology["circulation_network"]["traversable"] is False
    assert len(topology["circulation_network"]["space_boundary_contacts"]) == 6
    assert len(topology["vertical_connectivity_candidates"]) == 1
    assert topology["status"] == "REVIEW_REQUIRED"
    assert "fire_egress_and_exit_distances" in topology["unknowns"]


def test_topology_rejects_layout_hash_tampering():
    layout = _layout()
    layout["spaces"][0]["area_m2"] = 999.0

    try:
        build_spatial_topology(layout)
    except SpatialTopologyError as exc:
        assert exc.code == "TOPOLOGY_LAYOUT_HASH_INVALID"
    else:
        raise AssertionError("Tampered layout content must not be accepted")


def test_topology_rejects_declared_area_that_disagrees_with_polygon():
    layout = _layout()
    layout.pop("layout_hash")
    layout["spaces"][0]["area_m2"] = 21.0
    layout = _seal(layout)

    try:
        build_spatial_topology(layout)
    except SpatialTopologyError as exc:
        assert exc.code == "TOPOLOGY_AREA_MISMATCH"
    else:
        raise AssertionError("A mismatched declared area must fail closed")


def test_topology_reports_interior_overlaps_as_errors():
    layout = _seal({
        "project_id": "project-1",
        "project_version_id": "version-1",
        "world_model_hash": "a" * 64,
        "selected_alternative_id": "alternative-1",
        "spaces": [
            _space("a", "a", "office", "primary", 1, 0, 0, 5, 10),
            _space("b", "b", "meeting", "primary", 1, 4, 0, 9, 10),
        ],
        "adjacencies": [],
        "source_lineage": {"world_model_hash": "a" * 64},
    })

    topology = build_spatial_topology(layout)

    assert any(issue["code"] == "SPACE_INTERIOR_OVERLAP" for issue in topology["issues"])
    assert topology["status"] == "REVIEW_REQUIRED"


def test_spatial_topology_api_routes_are_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/spatial-topology/generate" in paths
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/spatial-topology" in paths
