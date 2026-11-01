from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.domains.commands.executor import execute_semantic_command
from app.domains.commands.preview import preview_command
from app.domains.commands.schemas import CommandEnvelope
from app.domains.program.service import build_program
from app.domains.semantic_model.editing import initial_designer_state, undo
from app.domains.semantic_model.service import compile_semantic_model


def world_fixture():
    model = {
        "project_id": "program-area-project",
        "project_version_id": "program-area-version",
        "site": {
            "area": {"value": 10000.0, "unit": "m2"},
            "width": {"value": 100.0, "unit": "m"},
            "depth": {"value": 100.0, "unit": "m"},
            "location": {},
        },
        "building": {
            "use": "office",
            "floor_count": 2,
            "height": {"value": 8.0, "unit": "m"},
            "floor_to_floor_height": {"value": 4.0, "unit": "m"},
            "target_gfa": {"value": 1000.0, "unit": "m2"},
            "coverage": 0.1,
        },
        "levels": [
            {
                "level_number": number,
                "elevation": {"value": (number - 1) * 4.0, "unit": "m"},
                "floor_to_floor_height": {"value": 4.0, "unit": "m"},
                "area": {"value": 500.0, "unit": "m2"},
            }
            for number in (1, 2)
        ],
        "spaces": [],
        "properties": {"footprint_width_m": 25.0, "footprint_depth_m": 20.0},
        "provenance": {},
        "designer_state": initial_designer_state(),
    }
    model["semantic_model"] = compile_semantic_model(model)
    return model


def set_program_area_command(area_m2: float = 200.0) -> CommandEnvelope:
    return CommandEnvelope(
        command_id="set-program-area-1",
        type="SetProgramArea",
        schema_version=1,
        project_id="program-area-project",
        version_id="program-area-version",
        base_revision_hash="program-revision-1",
        idempotency_key="set-program-area-idempotency-1",
        mode="commit",
        reason="Set reviewed open-work target",
        payload={"space_type": "open_work", "area_m2": area_m2},
    )


def test_set_program_area_updates_canonical_target_and_supports_undo():
    model = world_fixture()
    state = model["designer_state"]
    building = next(
        item for item in model["semantic_model"]["elements"]
        if item["element_type"] == "Building"
    )
    command = set_program_area_command()

    preview = preview_command(command.model_copy(update={"mode": "preview"}))
    assert preview.accepted is True
    assert preview.executable is True

    result = execute_semantic_command(model, state, command, "architect-1", "program-revision-1")

    assert result.status == "committed"
    assert model["properties"]["program_area_targets"] == {"open_work": 200.0}
    updated = next(
        item for item in model["semantic_model"]["elements"]
        if item["id"] == building["id"]
    )
    assert updated["properties"]["program_area_targets"]["value"] == {"open_work": 200.0}

    undo(model, state, "architect-1")
    assert model["properties"]["program_area_targets"] == {}


def test_program_generation_applies_explicit_targets_and_preserves_gfa():
    requirements = [
        SimpleNamespace(
            id="requirement-gfa",
            parameter="target_gfa",
            status="CONFIRMED",
            normalized_value_json=1000.0,
        ),
        SimpleNamespace(
            id="requirement-floors",
            parameter="floor_count",
            status="CONFIRMED",
            normalized_value_json=2,
        ),
    ]
    world = SimpleNamespace(
        model_json={
            "site": {"area": {"value": 10000.0}},
            "properties": {"program_area_targets": {"open_work": 200.0}},
        },
        model_hash="program-world-hash",
    )

    program = build_program(requirements, world)

    open_work = next(space for space in program["spaces"] if space["space_type"] == "open_work")
    assert open_work["target_area_m2"] == 200.0
    assert open_work["source"] == "human_review_program_target"
    assert sum(space["target_area_m2"] for space in program["spaces"]) == pytest.approx(1000.0)
    assert program["provenance"]["program_area_targets"] == {"open_work": 200.0}


def test_program_generation_rejects_explicit_targets_that_exceed_gfa():
    requirements = [
        SimpleNamespace(
            id="requirement-gfa",
            parameter="target_gfa",
            status="CONFIRMED",
            normalized_value_json=1000.0,
        ),
        SimpleNamespace(
            id="requirement-floors",
            parameter="floor_count",
            status="CONFIRMED",
            normalized_value_json=2,
        ),
    ]
    world = SimpleNamespace(
        model_json={
            "site": {"area": {"value": 10000.0}},
            "properties": {"program_area_targets": {"open_work": 1200.0}},
        },
        model_hash="program-world-hash",
    )

    with pytest.raises(HTTPException) as exc_info:
        build_program(requirements, world)
    assert exc_info.value.detail["error"]["code"] == "PROGRAM_AREA_TARGETS_EXCEED_GFA"


def test_set_program_area_respects_building_lock():
    model = world_fixture()
    state = model["designer_state"]
    building = next(
        item for item in model["semantic_model"]["elements"]
        if item["element_type"] == "Building"
    )
    state["locks"][building["id"]] = {"locked": True, "reason": "reviewed"}
    command = set_program_area_command()

    with pytest.raises(ValueError, match="SEMANTIC_ELEMENT_LOCKED"):
        execute_semantic_command(model, state, command, "architect-1", "program-revision-1")

    assert "program_area_targets" not in model["properties"]
