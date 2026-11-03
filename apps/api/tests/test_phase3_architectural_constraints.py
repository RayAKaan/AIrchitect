from __future__ import annotations

import hashlib
import json

import pytest

from app.domains.spatial_layout.constraints import (
    ArchitecturalConstraintError,
    compile_architectural_constraints,
)


WORLD_HASH = "a" * 64


def _seal(payload: dict, field: str) -> dict:
    value = dict(payload)
    value.pop(field, None)
    value[field] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return value


def _inputs():
    layout = {
        "project_id": "project-1",
        "project_version_id": "version-1",
        "world_model_hash": WORLD_HASH,
        "footprint": {
            "area_m2": 100.0,
            "boundary": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]],
        },
        "area_reconciliation": {
            "reconciled": True,
            "allocated_space_area_m2": 800.0,
            "selected_concept_gfa_m2": 800.0,
        },
        "spaces": [{"id": "space-1"}],
        "adjacencies": [{
            "from": "lobby", "to": "work", "required": True, "status": "SATISFIED",
        }],
        "unknowns": ["egress_routes"],
    }
    layout = _seal(layout, "layout_hash")
    topology = {
        "world_model_hash": WORLD_HASH,
        "layout_hash": layout["layout_hash"],
        "nodes": [{"id": "space-1"}],
        "edges": [],
        "issues": [],
        "circulation_network": {"status": "CONTACT_GRAPH_ONLY"},
        "unknowns": ["door_and_egress_geometry"],
    }
    topology = _seal(topology, "topology_hash")
    slab_boundary = [
        {"x": 0.0, "y": 0.0, "z": 0.0},
        {"x": 10.0, "y": 0.0, "z": 0.0},
        {"x": 10.0, "y": 8.0, "z": 0.0},
        {"x": 0.0, "y": 8.0, "z": 0.0},
        {"x": 0.0, "y": 0.0, "z": 0.0},
    ]
    elements = {
        "source_lineage": {
            "world_model_hash": WORLD_HASH,
            "layout_hash": layout["layout_hash"],
            "topology_hash": topology["topology_hash"],
        },
        "candidates": [
            {
                "candidate_id": "wall-1",
                "element_type": "Wall",
                "source_space_ids": ["space-1"],
                "properties": {
                    "start_m": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "end_m": {"x": 5.0, "y": 0.0, "z": 0.0},
                    "length_m": 5.0,
                    "height_m": 3.0,
                    "thickness_m": 0.2,
                },
                "missing_parameters": [],
            },
            {
                "candidate_id": "slab-1",
                "element_type": "Slab",
                "source_space_ids": ["space-1"],
                "properties": {
                    "boundary_m": slab_boundary,
                    "area_m2": 80.0,
                    "thickness_m": 0.25,
                },
                "missing_parameters": [],
            },
        ],
        "unknowns": [],
    }
    elements = _seal(elements, "elements_hash")
    envelope = {
        "buildable_polygon": {
            "type": "Polygon",
            "coordinates": [[
                [0.0, 0.0], [20.0, 0.0], [20.0, 20.0],
                [0.0, 20.0], [0.0, 0.0],
            ]],
        },
        "max_footprint_m2": 200.0,
        "max_gfa_m2": 1000.0,
    }
    envelope = _seal(envelope, "envelope_hash")
    return layout, topology, elements, envelope


def test_constraint_engine_separates_hard_passes_from_unknown_access_and_egress():
    layout, topology, elements, envelope = _inputs()
    result = compile_architectural_constraints(
        layout, topology, elements, envelope, world_model_hash=WORLD_HASH
    )

    assert result["status"] == "REVIEW_REQUIRED"
    assert result["summary"]["hard_constraints_passed"] is True
    assert result["summary"]["failed"] == 0
    assert result["summary"]["unknown"] > 0
    statuses = {item["code"]: item["status"] for item in result["constraints"]}
    assert statuses["PROGRAM_AREA_RECONCILIATION"] == "PASS"
    assert statuses["FOOTPRINT_WITHIN_BUILDABLE_ENVELOPE"] == "PASS"
    assert statuses["WALL_AXIS_VALID"] == "PASS"
    assert statuses["SLAB_BOUNDARY_AND_AREA_VALID"] == "PASS"
    assert statuses["TRAVERSABLE_CIRCULATION"] == "UNKNOWN"


def test_constraint_engine_blocks_footprint_and_gfa_hard_limit_violations():
    layout, topology, elements, envelope = _inputs()
    envelope["max_footprint_m2"] = 50.0
    envelope["max_gfa_m2"] = 700.0
    envelope = _seal(envelope, "envelope_hash")

    result = compile_architectural_constraints(
        layout, topology, elements, envelope, world_model_hash=WORLD_HASH
    )
    assert result["status"] == "BLOCKED"
    assert result["summary"]["failed"] == 2


def test_constraint_engine_fails_closed_on_stale_architectural_lineage():
    layout, topology, elements, envelope = _inputs()
    elements["source_lineage"]["topology_hash"] = "b" * 64
    elements = _seal(elements, "elements_hash")

    with pytest.raises(ArchitecturalConstraintError) as raised:
        compile_architectural_constraints(
            layout, topology, elements, envelope, world_model_hash=WORLD_HASH
        )
    assert raised.value.code == "CONSTRAINT_ELEMENT_LINEAGE_MISMATCH"


def test_constraint_engine_rejects_invalid_slab_geometry_as_hard_failure():
    layout, topology, elements, envelope = _inputs()
    elements["candidates"][1]["properties"]["area_m2"] = 90.0
    elements = _seal(elements, "elements_hash")

    result = compile_architectural_constraints(
        layout, topology, elements, envelope, world_model_hash=WORLD_HASH
    )
    slab = next(item for item in result["constraints"] if item["code"] == "SLAB_BOUNDARY_AND_AREA_VALID")
    assert slab["status"] == "FAIL"
    assert result["status"] == "BLOCKED"


def test_constraint_engine_requires_current_payload_hashes():
    layout, topology, elements, envelope = _inputs()
    layout["footprint"]["area_m2"] = 999.0

    with pytest.raises(ArchitecturalConstraintError) as raised:
        compile_architectural_constraints(
            layout, topology, elements, envelope, world_model_hash=WORLD_HASH
        )
    assert raised.value.code == "CONSTRAINT_LAYOUT_HASH_INVALID"


def test_architectural_constraint_evaluation_route_is_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert (
        "/api/v1/projects/{project_id}/versions/{version_ref}/architectural-elements/constraints"
        in paths
    )
