from types import SimpleNamespace

import pytest

from app.domains.commands.executor import execute_semantic_command
from app.domains.commands.preview import preview_command
from app.domains.commands.schemas import CommandEnvelope
from app.domains.design.config import DEFAULT_CONFIG
from app.domains.design.geometry_ir import GeometryValidator, MassingGeometryEngine
from app.domains.semantic_model.editing import initial_designer_state, redo, undo
from app.domains.semantic_model.service import compile_semantic_model


def world_fixture():
    model = {
        "project_id": "move-building-project",
        "project_version_id": "move-building-version",
        "site": {
            "area": {"value": 10000.0, "unit": "m2"},
            "width": {"value": 100.0, "unit": "m"},
            "depth": {"value": 100.0, "unit": "m"},
            "location": {},
        },
        "building": {
            "use": "office",
            "floor_count": 1,
            "height": {"value": 4.0, "unit": "m"},
            "floor_to_floor_height": {"value": 4.0, "unit": "m"},
            "target_gfa": {"value": 400.0, "unit": "m2"},
            "coverage": 0.04,
        },
        "levels": [{
            "level_number": 1,
            "elevation": {"value": 0.0, "unit": "m"},
            "floor_to_floor_height": {"value": 4.0, "unit": "m"},
            "area": {"value": 400.0, "unit": "m2"},
        }],
        "spaces": [],
        "properties": {"footprint_width_m": 20.0, "footprint_depth_m": 20.0},
        "provenance": {},
        "designer_state": initial_designer_state(),
    }
    model["semantic_model"] = compile_semantic_model(model)
    return model


def move_command(element_id, translation):
    return CommandEnvelope(
        command_id="move-building-1",
        type="MoveBuilding",
        schema_version=1,
        project_id="move-building-project",
        version_id="move-building-version",
        base_revision_hash="world-hash-1",
        idempotency_key="move-building-key-1",
        mode="commit",
        reason="Move the building to align with the site frontage",
        payload={"element_id": element_id, "translation_m": translation},
    )


def test_move_building_is_executable_and_updates_canonical_world_model():
    model = world_fixture()
    state = model["designer_state"]
    building = next(item for item in model["semantic_model"]["elements"] if item["element_type"] == "Building")
    command = move_command(building["id"], {"x": 5, "y": -2, "z": 1})

    preview = preview_command(command.model_copy(update={"mode": "preview"}))
    assert preview.accepted is True
    assert preview.executable is True

    result = execute_semantic_command(model, state, command, "actor-1", "world-hash-1")

    assert result.status == "committed"
    assert model["properties"]["building_translation_m"] == {"x": 5.0, "y": -2.0, "z": 1.0}
    updated_building = next(item for item in model["semantic_model"]["elements"] if item["id"] == building["id"])
    assert updated_building["properties"]["translation_m"]["value"] == {"x": 5.0, "y": -2.0, "z": 1.0}

    undo(model, state, "actor-1")
    assert model["properties"]["building_translation_m"] == {"x": 0.0, "y": 0.0, "z": 0.0}
    redo(model, state, "actor-1")
    assert model["properties"]["building_translation_m"] == {"x": 5.0, "y": -2.0, "z": 1.0}


def test_move_building_rejects_a_translation_that_leaves_the_site_without_mutation():
    model = world_fixture()
    state = model["designer_state"]
    building = next(item for item in model["semantic_model"]["elements"] if item["element_type"] == "Building")
    command = move_command(building["id"], {"x": 50, "y": 0, "z": 0})

    with pytest.raises(ValueError, match="BUILDING_MOVE_OUTSIDE_SITE"):
        execute_semantic_command(model, state, command, "actor-1", "world-hash-1")

    assert "building_translation_m" not in model["properties"]
    assert state["history"] == []


def test_massing_geometry_applies_the_canonical_building_translation():
    candidate = SimpleNamespace(
        candidate_key="balanced-1",
        assumptions=[],
        parameters={
            "footprint_width_m": 20.0,
            "footprint_depth_m": 20.0,
            "floor_count": 1,
            "floor_to_floor_height_m": 4.0,
            "setback_m": 0.0,
            "orientation_degrees": 0.0,
            "core_ratio": 0.1,
            "translation_m": {"x": 5.0, "y": -2.0, "z": 3.0},
        },
        metrics={
            "building_height_m": 4.0,
            "gross_floor_area_m2": 400.0,
            "building_footprint_m2": 400.0,
            "site_coverage_ratio": 0.04,
            "parking_count": None,
        },
    )
    engine = MassingGeometryEngine(DEFAULT_CONFIG)
    geometry = engine.generate(candidate, "alternative-1", 100.0, 100.0)
    mass = geometry.masses[0]

    assert mass.transform.translation == (45.0, 38.0, 3.0)
    assert geometry.floor_plates[0].transform.translation == (45.0, 38.0, 3.0)
    assert GeometryValidator(DEFAULT_CONFIG).validate(geometry, candidate).valid


def rotate_command(element_id, angle_deg):
    return CommandEnvelope(
        command_id="rotate-building-1",
        type="RotateBuilding",
        schema_version=1,
        project_id="move-building-project",
        version_id="move-building-version",
        base_revision_hash="world-hash-1",
        idempotency_key="rotate-building-key-1",
        mode="commit",
        reason="Rotate the building to align with the street",
        payload={"element_id": element_id, "angle_deg": angle_deg},
    )


def test_rotate_building_updates_canonical_rotation_and_supports_undo_redo():
    model = world_fixture()
    state = model["designer_state"]
    building = next(item for item in model["semantic_model"]["elements"] if item["element_type"] == "Building")
    command = rotate_command(building["id"], 90)

    preview = preview_command(command.model_copy(update={"mode": "preview"}))
    assert preview.accepted is True
    assert preview.executable is True

    result = execute_semantic_command(model, state, command, "actor-1", "world-hash-1")

    assert result.status == "committed"
    assert model["properties"]["building_rotation_deg"] == 90.0
    updated_building = next(item for item in model["semantic_model"]["elements"] if item["id"] == building["id"])
    assert updated_building["properties"]["rotation_deg"]["value"] == 90.0

    undo(model, state, "actor-1")
    assert model["properties"]["building_rotation_deg"] == 0.0
    redo(model, state, "actor-1")
    assert model["properties"]["building_rotation_deg"] == 90.0


def test_rotate_building_rejects_a_rotated_footprint_that_exceeds_site_bounds():
    model = world_fixture()
    model["properties"]["footprint_width_m"] = 100.0
    model["properties"]["footprint_depth_m"] = 100.0
    model["semantic_model"] = compile_semantic_model(model)
    state = model["designer_state"]
    building = next(item for item in model["semantic_model"]["elements"] if item["element_type"] == "Building")

    with pytest.raises(ValueError, match="BUILDING_TRANSFORM_OUTSIDE_SITE"):
        execute_semantic_command(
            model, state, rotate_command(building["id"], 45), "actor-1", "world-hash-1"
        )

    assert "building_rotation_deg" not in model["properties"]
    assert state["history"] == []


def test_massing_geometry_rotates_mass_floor_plates_cores_and_grid_together():
    candidate = SimpleNamespace(
        candidate_key="rotated-1",
        assumptions=[],
        parameters={
            "footprint_width_m": 20.0,
            "footprint_depth_m": 10.0,
            "floor_count": 1,
            "floor_to_floor_height_m": 4.0,
            "setback_m": 0.0,
            "orientation_degrees": 0.0,
            "rotation_deg": 90.0,
            "core_ratio": 0.1,
            "translation_m": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        metrics={
            "building_height_m": 4.0,
            "gross_floor_area_m2": 200.0,
            "building_footprint_m2": 200.0,
            "site_coverage_ratio": 0.02,
            "parking_count": None,
        },
    )
    geometry = MassingGeometryEngine(DEFAULT_CONFIG).generate(candidate, "alternative-rotated", 100.0, 100.0)

    assert geometry.masses[0].transform.translation == pytest.approx((55.0, 40.0, 0.0))
    assert geometry.masses[0].transform.rotation_degrees == (0.0, 0.0, 90.0)
    assert geometry.floor_plates[0].transform.rotation_degrees == (0.0, 0.0, 90.0)
    assert geometry.cores[0].transform.rotation_degrees == (0.0, 0.0, 90.0)
    assert geometry.structural_grids[0].transform.rotation_degrees == (0.0, 0.0, 90.0)
    assert GeometryValidator(DEFAULT_CONFIG).validate(geometry, candidate).valid
