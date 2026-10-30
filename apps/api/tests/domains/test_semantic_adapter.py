from __future__ import annotations

import pytest

from app.domains.commands.executor import execute_semantic_command
from app.domains.commands.schemas import CommandEnvelope
from app.domains.commands.semantic_adapter import semantic_edit_from_command, supports_semantic_command
from app.domains.semantic_model.editing import initial_designer_state
from app.domains.semantic_model.service import compile_semantic_model


def test_lock_entity_updates_canonical_designer_state() -> None:
    model = {
        "semantic_model": {
            "elements": [
                {"id": "space-1", "element_type": "Space", "type": "Space", "name": "Office"},
            ],
        },
    }
    state = {"locks": {}, "history": [], "undo_stack": [], "redo_stack": []}
    command = CommandEnvelope(
        command_id="lock-space-1",
        type="LockEntity",
        schema_version=1,
        project_id="project-1",
        version_id="version-1",
        base_revision_hash="revision-hash",
        idempotency_key="lock-space-idempotency-1",
        mode="commit",
        reason="protect reviewed space",
        payload={"element_id": "space-1"},
    )

    result = execute_semantic_command(model, state, command, "actor-1", "revision-hash")

    assert result.status == "committed"
    assert result.canonical_mutation is True
    assert state["locks"]["space-1"]["locked"] is True
    assert state["locks"]["space-1"]["reason"] == "protect reviewed space"
    assert model["designer_state"] is state


def test_redo_reapplies_the_last_undone_canonical_edit() -> None:
    model = {
        "project_id": "project-1",
        "project_version_id": "version-1",
        "site": {
            "area": {"value": 10000.0, "unit": "m2"},
            "width": {"value": 100.0, "unit": "m"},
            "depth": {"value": 100.0, "unit": "m"},
            "orientation": {"value": 0.0, "unit": "degree"},
            "location": {},
        },
        "building": {
            "use": "residential",
            "floor_count": 1,
            "floor_to_floor_height": {"value": 3.0, "unit": "m"},
            "height": {"value": 3.0, "unit": "m"},
            "target_gfa": {"value": 100.0, "unit": "m2"},
            "coverage": 0.1,
        },
        "levels": [{
            "level_number": 1,
            "elevation": {"value": 0.0, "unit": "m"},
            "floor_to_floor_height": {"value": 3.0, "unit": "m"},
            "area": {"value": 100.0, "unit": "m2"},
        }],
        "spaces": [{
            "id": "space-1",
            "name": "Office",
            "use": "office",
            "area": {"value": 10.0, "unit": "m2"},
            "level_number": 1,
        }],
        "designer_state": initial_designer_state(),
    }
    model["semantic_model"] = compile_semantic_model(model)
    state = model["designer_state"]
    space_id = next(
        element["id"] for element in model["semantic_model"]["elements"]
        if element["element_type"] == "Space"
    )

    resize = CommandEnvelope(
        command_id="resize-space", type="ResizeSpace", schema_version=1,
        project_id="project-1", version_id="version-1", base_revision_hash="revision-1",
        idempotency_key="resize-space-key", mode="commit", reason="resize office",
        payload={"element_id": space_id, "area_m2": 20.0},
    )
    undo_command = CommandEnvelope(
        command_id="undo-resize", type="Undo", schema_version=1,
        project_id="project-1", version_id="version-1", base_revision_hash="revision-2",
        idempotency_key="undo-resize-key", mode="commit", reason="undo resize", payload={},
    )
    redo_command = CommandEnvelope(
        command_id="redo-resize", type="Redo", schema_version=1,
        project_id="project-1", version_id="version-1", base_revision_hash="revision-3",
        idempotency_key="redo-resize-key", mode="commit", reason="redo resize", payload={},
    )

    resized = execute_semantic_command(model, state, resize, "actor-1", "revision-1")
    assert resized.status == "committed"
    assert model["spaces"][0]["area"]["value"] == 20.0

    undone = execute_semantic_command(model, state, undo_command, "actor-1", "revision-2")
    assert undone.status == "committed"
    assert model["spaces"][0]["area"]["value"] == 10.0
    assert state["redo_stack"]

    redone = execute_semantic_command(model, state, redo_command, "actor-1", "revision-3")
    assert redone.status == "committed"
    assert model["spaces"][0]["area"]["value"] == 20.0
    assert state["redo_stack"] == []
    assert state["undo_stack"]
    assert model["designer_state"] is state


@pytest.mark.parametrize(
    ("command_type", "payload"),
    [
        ("MoveBuilding", {"element_id": "building-1", "translation_m": {"x": 1, "y": 0, "z": 0}}),
        ("RotateBuilding", {"element_id": "building-1", "angle_deg": 15}),
        ("MoveSpace", {"element_id": "space-1", "translation_m": {"x": 1, "y": 0, "z": 0}}),
    ],
)
def test_geometric_commands_are_not_claimed_by_semantic_property_adapter(
    command_type: str, payload: dict[str, object],
) -> None:
    command = CommandEnvelope(
        command_id=f"command-{command_type}",
        type=command_type,
        schema_version=1,
        project_id="project-1",
        version_id="version-1",
        base_revision_hash="revision-hash",
        idempotency_key=f"idempotency-{command_type}-1",
        mode="commit",
        reason="test command adapter boundary",
        payload=payload,
    )

    assert supports_semantic_command(command_type) is False
    with pytest.raises(ValueError, match="not handled by semantic adapter"):
        semantic_edit_from_command(command)
