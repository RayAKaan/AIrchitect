from __future__ import annotations

import hashlib
import json

import pytest

from app.domains.spatial_layout.architectural_elements import (
    ArchitecturalElementError,
    compile_architectural_elements,
)
from app.domains.spatial_layout.topology import build_spatial_topology


def _seal(payload: dict) -> dict:
    value = dict(payload)
    value["layout_hash"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return value


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
            {
                "id": "room-a",
                "level_number": 1,
                "area_m2": 50.0,
                "boundary": [
                    [0.0, 0.0, 0.0],
                    [5.0, 0.0, 0.0],
                    [5.0, 10.0, 0.0],
                    [0.0, 10.0, 0.0],
                    [0.0, 0.0, 0.0],
                ],
            },
            {
                "id": "room-b",
                "level_number": 1,
                "area_m2": 50.0,
                "boundary": [
                    [5.0, 0.0, 0.0],
                    [10.0, 0.0, 0.0],
                    [10.0, 10.0, 0.0],
                    [5.0, 10.0, 0.0],
                    [5.0, 0.0, 0.0],
                ],
            },
        ],
        "adjacencies": [],
        "source_lineage": {
            "world_model_hash": "a" * 64,
            "program_hash": "b" * 64,
            "envelope_hash": "c" * 64,
            "alternative_id": "alternative-1",
        },
    })


def _topology(layout: dict) -> dict:
    return build_spatial_topology(layout)


def _reseal_topology(payload: dict) -> dict:
    value = dict(payload)
    value.pop("topology_hash", None)
    value["topology_hash"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return value


def test_element_compiler_derives_unique_perimeter_and_partition_wall_axes():
    layout = _layout()
    topology = _topology(layout)

    first = compile_architectural_elements(layout, topology)
    second = compile_architectural_elements(layout, topology)

    assert first["elements_hash"] == second["elements_hash"]
    assert first["counts"] == {
        "wall_candidates": 7,
        "slab_candidates": 1,
        "perimeter_walls": 6,
        "partition_walls": 1,
    }
    partition = next(item for item in first["candidates"] if item["wall_classification"] == "PARTITION")
    assert partition["source_space_ids"] == ["room-a", "room-b"]
    assert partition["status"] == "UNDERCONSTRAINED"
    assert set(partition["missing_parameters"]) == {"height_m", "thickness_m"}
    assert first["not_generated"] == ["roof", "doors", "windows", "stairs", "ramps"]


def test_explicit_wall_thickness_is_preserved_as_a_design_parameter():
    layout = _layout()
    topology = _topology(layout)

    result = compile_architectural_elements(layout, topology, default_wall_thickness_m=0.2)

    walls = [item for item in result["candidates"] if item["element_type"] == "Wall"]
    assert all(item["properties"]["thickness_m"] == 0.2 for item in walls)
    assert all("thickness_m" not in item["missing_parameters"] for item in walls)
    assert all("not a code minimum" in item["assumptions"][0] for item in walls)
    slabs = [item for item in result["candidates"] if item["element_type"] == "Slab"]
    assert all("thickness_m" in item["missing_parameters"] for item in slabs)


@pytest.mark.parametrize("thickness", [0, -0.1, 1.01, float("nan"), True])
def test_wall_thickness_rejects_invalid_values(thickness):
    with pytest.raises(ArchitecturalElementError) as exc:
        compile_architectural_elements(_layout(), _topology(_layout()), default_wall_thickness_m=thickness)
    assert exc.value.code == "ELEMENT_WALL_THICKNESS_INVALID"


def test_element_compiler_rejects_tampered_topology_and_mismatched_layout():
    layout = _layout()
    topology = _topology(layout)
    topology["nodes"][0]["area_m2"] = 999.0

    with pytest.raises(ArchitecturalElementError) as exc:
        compile_architectural_elements(layout, topology)
    assert exc.value.code == "ELEMENT_TOPOLOGY_HASH_INVALID"


def test_element_compiler_rejects_non_planar_room_boundaries():
    layout = _layout()
    layout.pop("layout_hash")
    layout["spaces"][0]["boundary"][2][2] = 0.25
    layout = _seal(layout)

    with pytest.raises(ArchitecturalElementError) as exc:
        compile_architectural_elements(layout, _topology(layout))

    assert exc.value.code == "ELEMENT_BOUNDARY_NON_PLANAR"
    assert exc.value.context["space_id"] == "room-a"


def test_element_compiler_rejects_non_finite_coordinates():
    layout = _layout()
    layout.pop("layout_hash")
    layout["spaces"][0]["boundary"][0][0] = float("inf")
    layout = _seal(layout)

    topology = {
        "world_model_hash": layout["world_model_hash"],
        "source_lineage": {"layout_hash": layout["layout_hash"]},
    }
    topology["topology_hash"] = hashlib.sha256(
        json.dumps(topology, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    with pytest.raises(ArchitecturalElementError) as exc:
        compile_architectural_elements(layout, topology)
    assert exc.value.code == "ELEMENT_BOUNDARY_INVALID"


def test_element_compiler_rejects_topology_from_another_layout():
    layout = _layout()
    other_layout = _layout()
    other_layout["spaces"][0]["area_m2"] = 49.0
    other_layout["spaces"][0]["boundary"][1][0] = 4.9
    other_layout["spaces"][0]["boundary"][2][0] = 4.9
    other_layout.pop("layout_hash")
    other_layout = _seal(other_layout)

    with pytest.raises(ArchitecturalElementError) as exc:
        compile_architectural_elements(layout, _topology(other_layout))
    assert exc.value.code == "ELEMENT_TOPOLOGY_STALE"


def test_wall_cad_intent_requires_explicit_axis_endpoints_and_storey_placement():
    from app.domains.semantic_model.service import compile_parametric_geometry

    def prop(value, unit=None, data_type="number"):
        return {"value": value, "unit": unit, "data_type": data_type}

    storey = {
        "id": "storey-1",
        "element_type": "Storey",
        "properties": {
            "level_number": prop(1, "count", "integer"),
            "elevation_m": prop(0.0, "m"),
        },
    }
    wall = {
        "id": "wall-1",
        "element_type": "Wall",
        "properties": {
            "length_m": prop(5.0, "m"),
            "height_m": prop(3.0, "m"),
            "thickness_m": prop(0.2, "m"),
        },
    }
    semantic = {
        "project_id": "project-1",
        "project_version_id": "version-1",
        "source_world_model_hash": "a" * 64,
        "elements": [storey, wall],
        "relationships": [{
            "source_id": "storey-1",
            "relationship_type": "hosts_element",
            "target_id": "wall-1",
        }],
    }
    world = {"building": {}, "properties": {}}

    missing_axis = compile_parametric_geometry(world, semantic)
    intent = next(item for item in missing_axis["intents"] if item["element_id"] == "wall-1")
    assert intent["status"] == "UNDERCONSTRAINED"
    assert set(intent["missing_parameters"]) == {"start_m", "end_m"}

    wall["properties"]["start_m"] = prop({"x": 0.0, "y": 0.0, "z": 0.0}, "m", "vector3")
    wall["properties"]["end_m"] = prop({"x": 5.0, "y": 0.0, "z": 0.0}, "m", "vector3")
    complete_axis = compile_parametric_geometry(world, semantic)
    wall_intent = next(item for item in complete_axis["intents"] if item["element_id"] == "wall-1")
    assert wall_intent["status"] == "READY_FOR_CAD_ADAPTER"
    assert wall_intent["parameters"]["start_m"]["x"] == 0.0
    assert wall_intent["parameters"]["end_m"]["x"] == 5.0


def test_architectural_element_proposal_routes_are_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert (
        "/api/v1/projects/{project_id}/versions/{version_ref}/architectural-elements/generate"
        in paths
    )
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/architectural-elements" in paths
    assert (
        "/api/v1/projects/{project_id}/versions/{version_ref}/architectural-elements/commit"
        in paths
    )


def test_element_compiler_nodes_t_junctions_into_unique_shared_wall_segments():
    layout = _seal({
        "schema_version": "phase3-spatial-layout-v1",
        "project_id": "project-1",
        "project_version_id": "version-1",
        "world_model_hash": "a" * 64,
        "selected_alternative_id": "alternative-1",
        "spaces": [
            {
                "id": "left",
                "level_number": 1,
                "area_m2": 50.0,
                "boundary": [
                    [0.0, 0.0, 0.0], [5.0, 0.0, 0.0],
                    [5.0, 10.0, 0.0], [0.0, 10.0, 0.0],
                    [0.0, 0.0, 0.0],
                ],
            },
            {
                "id": "right-lower",
                "level_number": 1,
                "area_m2": 25.0,
                "boundary": [
                    [5.0, 0.0, 0.0], [10.0, 0.0, 0.0],
                    [10.0, 5.0, 0.0], [5.0, 5.0, 0.0],
                    [5.0, 0.0, 0.0],
                ],
            },
            {
                "id": "right-upper",
                "level_number": 1,
                "area_m2": 25.0,
                "boundary": [
                    [5.0, 5.0, 0.0], [10.0, 5.0, 0.0],
                    [10.0, 10.0, 0.0], [5.0, 10.0, 0.0],
                    [5.0, 5.0, 0.0],
                ],
            },
        ],
        "adjacencies": [],
        "source_lineage": {"world_model_hash": "a" * 64},
    })

    result = compile_architectural_elements(layout, _topology(layout))
    shared_vertical = [
        item for item in result["candidates"]
        if item["wall_classification"] == "PARTITION"
        and item["properties"]["start_m"]["x"] == 5.0
        and item["properties"]["end_m"]["x"] == 5.0
    ]

    assert len(shared_vertical) == 2
    assert {tuple(item["source_space_ids"]) for item in shared_vertical} == {
        ("left", "right-lower"),
        ("left", "right-upper"),
    }
    assert result["counts"]["partition_walls"] == 3
    assert len({item["candidate_id"] for item in result["candidates"]}) == len(result["candidates"])


def test_element_compiler_derives_stable_floor_slab_from_room_union():
    layout = _layout()
    topology = _topology(layout)
    first = compile_architectural_elements(layout, topology)
    second = compile_architectural_elements(layout, topology)

    slab = next(item for item in first["candidates"] if item["element_type"] == "Slab")
    repeated = next(item for item in second["candidates"] if item["element_type"] == "Slab")
    assert slab["candidate_id"] == repeated["candidate_id"]
    assert slab["source_space_ids"] == ["room-a", "room-b"]
    assert slab["properties"]["area_m2"] == 100.0
    assert slab["properties"]["boundary_m"] == [
        {"x": 0.0, "y": 0.0, "z": 0.0},
        {"x": 10.0, "y": 0.0, "z": 0.0},
        {"x": 10.0, "y": 10.0, "z": 0.0},
        {"x": 0.0, "y": 10.0, "z": 0.0},
        {"x": 0.0, "y": 0.0, "z": 0.0},
    ]
    assert slab["status"] == "UNDERCONSTRAINED"
    assert slab["missing_parameters"] == ["thickness_m"]


def test_element_compiler_does_not_fill_floor_plate_voids():
    layout = _layout()
    layout.pop("layout_hash")
    layout["spaces"] = [
        {
            "id": "south",
            "level_number": 1,
            "area_m2": 20.0,
            "boundary": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 2.0, 0.0],
                         [0.0, 2.0, 0.0], [0.0, 0.0, 0.0]],
        },
        {
            "id": "north",
            "level_number": 1,
            "area_m2": 20.0,
            "boundary": [[0.0, 8.0, 0.0], [10.0, 8.0, 0.0], [10.0, 10.0, 0.0],
                         [0.0, 10.0, 0.0], [0.0, 8.0, 0.0]],
        },
        {
            "id": "west",
            "level_number": 1,
            "area_m2": 12.0,
            "boundary": [[0.0, 2.0, 0.0], [2.0, 2.0, 0.0], [2.0, 8.0, 0.0],
                         [0.0, 8.0, 0.0], [0.0, 2.0, 0.0]],
        },
        {
            "id": "east",
            "level_number": 1,
            "area_m2": 12.0,
            "boundary": [[8.0, 2.0, 0.0], [10.0, 2.0, 0.0], [10.0, 8.0, 0.0],
                         [8.0, 8.0, 0.0], [8.0, 2.0, 0.0]],
        },
    ]
    layout = _seal(layout)
    topology = _topology(layout)
    result = compile_architectural_elements(layout, topology)

    assert not any(item["element_type"] == "Slab" for item in result["candidates"])
    assert "slab_level_1_void_boundary_requires_explicit_opening_geometry" in result["unknowns"]


def test_element_compiler_rejects_topology_nodes_that_do_not_match_layout():
    layout = _layout()
    topology = _topology(layout)
    topology["nodes"] = topology["nodes"][:-1]
    topology = _reseal_topology(topology)

    with pytest.raises(ArchitecturalElementError) as exc:
        compile_architectural_elements(layout, topology)
    assert exc.value.code == "ELEMENT_TOPOLOGY_NODES_MISMATCH"
    assert exc.value.context["missing_node_ids"] == ["room-b"]


def test_element_compiler_rejects_non_manifold_shared_wall_segments():
    layout = _layout()
    layout.pop("layout_hash")
    duplicate = dict(layout["spaces"][0])
    duplicate["id"] = "room-c"
    layout["spaces"].append(duplicate)
    layout = _seal(layout)
    topology = _topology(layout)
    # Isolate the non-manifold ownership gate from the separate overlap gate.
    topology["issues"] = []
    topology = _reseal_topology(topology)

    with pytest.raises(ArchitecturalElementError) as exc:
        compile_architectural_elements(layout, topology)
    assert exc.value.code == "ELEMENT_BOUNDARY_NON_MANIFOLD"


def test_element_compiler_blocks_topology_geometry_errors():
    layout = _layout()
    topology = _topology(layout)
    topology["issues"] = [{
        "code": "SPACE_INTERIOR_OVERLAP",
        "severity": "ERROR",
        "space_ids": ["room-a", "room-b"],
    }]
    topology = _reseal_topology(topology)

    with pytest.raises(ArchitecturalElementError) as exc:
        compile_architectural_elements(layout, topology)
    assert exc.value.code == "ELEMENT_TOPOLOGY_INVALID"


def test_spatial_topology_and_element_regeneration_use_current_layout_dependencies():
    layout = _layout()
    expected_topology = _topology(layout)
    registry = RegenerationHandlerRegistry()

    topology_result = registry.execute(RegenerationInput(
        artifact_type="spatial_topology",
        source_revision_hash=layout["world_model_hash"],
        payload={},
        dependencies={"spatial_layout": {"payload": layout}},
    ))
    assert topology_result.payload["topology_hash"] == expected_topology["topology_hash"]

    expected_elements = compile_architectural_elements(layout, expected_topology)
    elements_result = registry.execute(RegenerationInput(
        artifact_type="architectural_elements",
        source_revision_hash=layout["world_model_hash"],
        payload={"regeneration_request": {"default_wall_thickness_m": None}},
        dependencies={
            "spatial_layout": {"payload": layout},
            "spatial_topology": {"payload": expected_topology},
        },
    ))
    expected_elements["regeneration_request"] = {"default_wall_thickness_m": None}
    expected_hash_input = dict(expected_elements)
    expected_hash_input.pop("elements_hash", None)
    expected_elements["elements_hash"] = canonical_hash(expected_hash_input)
    assert elements_result.payload["elements_hash"] == expected_elements["elements_hash"]
