from __future__ import annotations

from typing import Any

from app.domains.semantic_model.editing import edit_property, redo, set_lock, undo

from .schemas import CommandEnvelope

# This adapter owns only commands that map to editable semantic properties.
# Geometric transforms must be implemented by their canonical geometry/domain
# command path; they must never be routed through this property adapter.
SUPPORTED = {"ResizeSpace": "area_m2"}
EXECUTABLE_CONTROL_COMMAND_TYPES = frozenset({"LockEntity", "Undo", "Redo"})


def supports_semantic_command(command_type: str) -> bool:
    """Return whether the semantic command adapter owns this command."""
    return command_type in SUPPORTED or command_type in EXECUTABLE_CONTROL_COMMAND_TYPES


def semantic_edit_from_command(command: CommandEnvelope) -> tuple[str, str, Any]:
    """Translate a supported property command into the semantic edit primitive."""
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
    if command.type == "Redo":
        return redo(model, state, actor_id)
    if command.type == "LockEntity":
        element_id = command.payload.get("element_id")
        if not isinstance(element_id, str) or not element_id.strip():
            raise ValueError("element_id must be a non-empty string")
        event = set_lock(state, element_id, actor_id, True, command.reason)
        model["designer_state"] = state
        return event
    element_id, property_name, value = semantic_edit_from_command(command)
    return edit_property(model, state, element_id, property_name, value, actor_id, command.reason)
