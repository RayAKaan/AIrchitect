from __future__ import annotations

from typing import Any

from app.domains.semantic_model.editing import edit_property, set_lock, undo

from .schemas import CommandEnvelope

SUPPORTED = {"MoveBuilding": "translation_m", "RotateBuilding": "rotation_deg", "ResizeSpace": "area_m2"}


def semantic_edit_from_command(command: CommandEnvelope) -> tuple[str, str, Any]:
    """Translate a small, explicit command subset into the existing semantic mutation primitive."""
    if command.type not in SUPPORTED:
        raise ValueError(f"command is not handled by semantic adapter: {command.type}")
    element_id = command.payload.get("element_id")
    if not isinstance(element_id, str) or not element_id.strip():
        raise ValueError("element_id must be a non-empty string")
    property_name = SUPPORTED[command.type]
    if property_name not in command.payload:
        raise ValueError(f"missing payload field: {property_name}")
    return element_id, property_name, command.payload[property_name]


def apply_semantic_command(model: dict[str, Any], state: dict[str, Any], command: CommandEnvelope, actor_id: str) -> dict[str, Any]:
    if command.type == "Undo":
        return undo(model, state, actor_id)
    if command.type == "LockEntity":
        element_id = command.payload.get("element_id")
        if not isinstance(element_id, str) or not element_id.strip():
            raise ValueError("element_id must be a non-empty string")
        event = set_lock(state, element_id, actor_id, True, command.reason)
        model["designer_state"] = state
        return event
    element_id, property_name, value = semantic_edit_from_command(command)
    return edit_property(model, state, element_id, property_name, value, actor_id, command.reason)
