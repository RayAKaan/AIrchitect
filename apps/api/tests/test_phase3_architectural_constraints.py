from __future__ import annotations

import hashlib
import json

import pytest

from app.domains.spatial_layout.constraints import (
    ArchitecturalConstraintError,
    compile_architectural_constraints,
)
from app.domains.commands.regeneration import RegenerationPlan
from app.domains.commands.regeneration_engine import execution_steps
from app.domains.commands.regeneration_executor import RegenerationHandlerRegistry, RegenerationInput


WORLD_HASH = "a" * 64


def _seal(payload: dict, field: str) -> dict:
    value = dict(payload)
    value.pop(field, None)
    value[field] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return value


def _relink(layout, topology, elements, envelope):
    layout["source_lineage"]["envelope_hash"] = envelope["envelope_hash"]
    layout = _seal(layout, "layout_hash")
    topology["layout_hash"] = layout["layout_hash"]
    topology = _seal(topology, "topology_hash")
    elements["source_lineage"]["layout_hash"] = layout["layout_hash"]
    elements["source_lineage"]["topology_hash"] = topology["topology_hash"]
    elements = _seal(elements, "elements_hash")
    return layout, topology, elements


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
        "adjacencies": [
            {"from": "lobby", "to": "work", "required": True, "status": "SATISFIED"},
            {"from": "office", "to": "terrace", "required": False, "status": "DEFERRED_TO_TOPOLOGY"},
        ],
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
    layout["source_lineage"] = {"world_model_hash": WORLD_HASH, "envelope_hash": envelope["envelope_hash"]}
    layout = _seal(layout, "layout_hash")
    topology["layout_hash"] = layout["layout_hash"]
    topology = _seal(topology, "topology_hash")
    elements["source_lineage"]["layout_hash"] = layout["layout_hash"]
    elements["source_lineage"]["topology_hash"] = topology["topology_hash"]
    elements = _seal(elements, "elements_hash")
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
    preferred = next(item for item in result["constraints"] if item["code"] == "PREFERRED_PROGRAM_ADJACENCY")
    assert preferred["classification"] == "PREFERRED"
    assert preferred["status"] == "REVIEW_REQUIRED"


def test_constraint_engine_blocks_footprint_and_gfa_hard_limit_violations():
    layout, topology, elements, envelope = _inputs()
    envelope["max_footprint_m2"] = 50.0
    envelope["max_gfa_m2"] = 700.0
    envelope = _seal(envelope, "envelope_hash")
    layout, topology, elements = _relink(layout, topology, elements, envelope)

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


def test_explicitly_unsatisfied_required_adjacency_is_a_hard_failure():
    layout, topology, elements, envelope = _inputs()
    layout["adjacencies"][0]["status"] = "UNSATISFIED"
    layout = _seal(layout, "layout_hash")
    layout, topology, elements = _relink(layout, topology, elements, envelope)

    result = compile_architectural_constraints(
        layout, topology, elements, envelope, world_model_hash=WORLD_HASH
    )
    required = next(item for item in result["constraints"] if item["code"] == "REQUIRED_PROGRAM_ADJACENCY")
    assert required["classification"] == "HARD"
    assert required["status"] == "FAIL"
    assert result["status"] == "BLOCKED"


def test_missing_wall_dimensions_remain_unresolved_hard_constraints():
    layout, topology, elements, envelope = _inputs()
    wall = elements["candidates"][0]
    wall["properties"].pop("height_m")
    wall["properties"].pop("thickness_m")
    wall["missing_parameters"] = ["height_m", "thickness_m"]
    elements = _seal(elements, "elements_hash")

    result = compile_architectural_constraints(
        layout, topology, elements, envelope, world_model_hash=WORLD_HASH
    )
    wall_constraint = next(
        item for item in result["constraints"] if item["code"] == "WALL_DIMENSIONS_COMPLETE"
    )
    assert wall_constraint["classification"] == "HARD"
    assert wall_constraint["status"] == "UNKNOWN"
    assert result["summary"]["hard_unknown"] == 1
    assert result["summary"]["hard_constraints_passed"] is False
    assert result["status"] == "REVIEW_REQUIRED"


def test_phase3_regeneration_handlers_use_current_spatial_dependencies():
    layout, topology, elements, envelope = _inputs()
    registry = RegenerationHandlerRegistry()
    assert registry.supports("spatial_topology")
    assert registry.supports("architectural_elements")
    assert registry.supports("architectural_constraints")

    result = registry.execute(RegenerationInput(
        artifact_type="architectural_constraints",
        source_revision_hash=WORLD_HASH,
        payload={},
        dependencies={
            "spatial_layout": {"payload": layout},
            "spatial_topology": {"payload": topology},
            "architectural_elements": {"payload": elements},
            "planning_envelope": {"payload": envelope},
        },
    ))
    assert result.payload["constraints_hash"]
    assert result.output_hash
    assert result.payload["source_lineage"]["world_model_hash"] == WORLD_HASH


def test_regeneration_order_places_spatial_constraints_before_quantities():
    plan = RegenerationPlan(
        command_id="command-1",
        source_revision_hash=WORLD_HASH,
        groups=(
            "architectural_constraints",
            "quantities",
            "spatial_topology",
            "spatial_layout",
            "architectural_elements",
        ),
        requires_recomputation=True,
    )
    steps = execution_steps(plan)
    assert [step.group for step in steps] == [
        "spatial_layout",
        "spatial_topology",
        "architectural_elements",
        "architectural_constraints",
        "quantities",
    ]
