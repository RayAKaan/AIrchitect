from __future__ import annotations

from typing import Any

from .schemas import CommandEnvelope


def _find_element(model: dict[str, Any], element_id: str) -> dict[str, Any] | None:
    semantic = model.get("semantic_model")
    elements = semantic.get("elements", []) if isinstance(semantic, dict) else []
    return next((element for element in elements if element.get("id") == element_id), None)


def _element_type(element: dict[str, Any]) -> str | None:
    """Read the canonical semantic type without relying on legacy aliases."""
    value = element.get("element_type") or element.get("type")
    return value if isinstance(value, str) else None


def check_preconditions(model: dict[str, Any], state: dict[str, Any], command: CommandEnvelope) -> list[str]:
    """Return deterministic, fail-closed semantic precondition errors."""
    errors: list[str] = []
    if command.type in {"MoveBuilding", "RotateBuilding", "ResizeSpace", "MoveSpace", "LockEntity"}:
        element_id = command.payload.get("element_id")
        if not isinstance(element_id, str) or not element_id.strip():
            return ["element_id is required"]
        element = _find_element(model, element_id)
        if element is None:
            errors.append("SEMANTIC_ELEMENT_NOT_FOUND")
        lock = state.get("locks", {}).get(element_id, {})
        if lock.get("locked") and command.type != "LockEntity":
            errors.append("SEMANTIC_ELEMENT_LOCKED")
    if command.type == "ResizeSpace":
        element = _find_element(model, str(command.payload.get("element_id", "")))
        if element is not None and _element_type(element) != "Space":
            errors.append("COMMAND_TARGET_TYPE_MISMATCH: expected Space")
    if command.type in {"MoveBuilding", "RotateBuilding"}:
        element = _find_element(model, str(command.payload.get("element_id", "")))
        if element is not None and _element_type(element) != "Building":
            errors.append("COMMAND_TARGET_TYPE_MISMATCH: expected Building")
    if command.type == "MoveSpace":
        element = _find_element(model, str(command.payload.get("element_id", "")))
        if element is not None and _element_type(element) != "Space":
            errors.append("COMMAND_TARGET_TYPE_MISMATCH: expected Space")
    return errors
