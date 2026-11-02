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


def test_element_compiler_derives_unique_perimeter_and_partition_wall_axes():
    layout = _layout()
    topology = _topology(layout)

    first = compile_architectural_elements(layout, topology)
    second = compile_architectural_elements(layout, topology)

    assert first["elements_hash"] == second["elements_hash"]
    assert first["counts"] == {
        "wall_candidates": 7,
        "perimeter_walls": 6,
        "partition_walls": 1,
    }
    partition = next(item for item in first["candidates"] if item["wall_classification"] == "PARTITION")
    assert partition["source_space_ids"] == ["room-a", "room-b"]
    assert partition["status"] == "UNDERCONSTRAINED"
    assert set(partition["missing_parameters"]) == {"height_m", "thickness_m"}
    assert first["not_generated"] == ["slabs", "roof", "doors", "windows", "stairs", "ramps"]


def test_explicit_wall_thickness_is_preserved_as_a_design_parameter():
    layout = _layout()
    topology = _topology(layout)

    result = compile_architectural_elements(layout, topology, default_wall_thickness_m=0.2)

    assert all(item["properties"]["thickness_m"] == 0.2 for item in result["candidates"])
    assert all("thickness_m" not in item["missing_parameters"] for item in result["candidates"])
    assert all(
        "not a code minimum" in item["assumptions"][0]
        for item in result["candidates"]
    )


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


def test_element_compiler_rejects_non_finite_coordinates():
    layout = _layout()
    layout.pop("layout_hash")
    layout["spaces"][0]["boundary"][0][0] = float("inf")
    layout = _seal(layout)

    with pytest.raises(ArchitecturalElementError) as exc:
        compile_architectural_elements(layout, _topology(_layout()))
    assert exc.value.code == "ELEMENT_BOUNDARY_INVALID"


def test_element_compiler_rejects_topology_from_another_layout():
    layout = _layout()
    other_layout = _layout()
    other_layout["spaces"][0]["area_m2"] = 49.0
    other_layout.pop("layout_hash")
    other_layout = _seal(other_layout)

    with pytest.raises(ArchitecturalElementError) as exc:
        compile_architectural_elements(layout, _topology(other_layout))
    assert exc.value.code == "ELEMENT_TOPOLOGY_STALE"
