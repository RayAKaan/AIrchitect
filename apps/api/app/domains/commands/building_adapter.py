from __future__ import annotations

from typing import Any

from app.domains.semantic_model.editing import edit_properties

from .schemas import CommandEnvelope


def supports_building_command(command_type: str) -> bool:
    return command_type == "AddLevel"


def _quantity_value(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def apply_building_command(
    model: dict[str, Any],
    state: dict[str, Any],
    command: CommandEnvelope,
    actor_id: str,
) -> dict[str, Any]:
    """Append one contiguous storey and its elevation as one undoable edit."""
    if command.type != "AddLevel":
        raise ValueError(f"building adapter does not handle command: {command.type}")

    building_id = command.payload.get("building_id")
    if not isinstance(building_id, str) or not building_id.strip():
        raise ValueError("building_id must be a non-empty string")
    semantic = model.get("semantic_model") or {}
    building = next(
        (item for item in semantic.get("elements", []) if item.get("id") == building_id),
        None,
    )
    if building is None or building.get("element_type") != "Building":
        raise ValueError("COMMAND_TARGET_TYPE_MISMATCH: expected Building")

    levels = sorted(model.get("levels") or [], key=lambda row: int(row["level_number"]))
    current_count = int((model.get("building") or {}).get("floor_count") or len(levels))
    if current_count < 1 or len(levels) != current_count:
        raise ValueError("BUILDING_LEVEL_STATE_INCONSISTENT: canonical floor count and storey rows must agree")
    if current_count >= 100:
        raise ValueError("LEVEL_LIMIT_EXCEEDED: a building cannot exceed 100 levels")

    previous_level = levels[-1]
    previous_elevation = _quantity_value(previous_level.get("elevation"))
    if previous_elevation is None:
        raise ValueError("LEVEL_ELEVATION_UNKNOWN: the top storey's elevation must be known")
    requested_elevation = float(command.payload["elevation_m"])
    floor_to_floor = requested_elevation - previous_elevation
    if floor_to_floor <= 0 or floor_to_floor > 20:
        raise ValueError(
            "INVALID_NEW_LEVEL_ELEVATION: the new storey must be above the current top storey by at most 20 metres"
        )

    previous_storey = next(
        (
            item for item in semantic.get("elements", [])
            if item.get("element_type") == "Storey"
            and item.get("identity_key") == f"level:{current_count}"
        ),
        None,
    )
    if previous_storey is None:
        raise ValueError("STOREY_NOT_FOUND: the current top storey semantic element is required")

    return edit_properties(
        model,
        state,
        [
            {
                "element_id": building_id,
                "property_name": "floor_count",
                "value": current_count + 1,
            },
            {
                "element_id": previous_storey["id"],
                "property_name": "floor_to_floor_height_m",
                "value": floor_to_floor,
            },
        ],
        actor_id,
        command.reason,
    )
