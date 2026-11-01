from __future__ import annotations

import math
from typing import Any

from app.domains.semantic_model.editing import edit_property

from .schemas import CommandEnvelope
from .semantic_adapter import supports_semantic_command
from .program_adapter import supports_program_command
from .planning_adapter import supports_planning_command
from .building_adapter import supports_building_command


GEOMETRY_COMMAND_TYPES = frozenset({"MoveBuilding", "RotateBuilding", "MoveSpace"})


def supports_geometry_command(command_type: str) -> bool:
    return command_type in GEOMETRY_COMMAND_TYPES


def supports_command(command_type: str) -> bool:
    """Return whether a command has an executable canonical mutation adapter."""
    return (
        supports_semantic_command(command_type)
        or command_type in GEOMETRY_COMMAND_TYPES
        or supports_program_command(command_type)
        or supports_planning_command(command_type)
        or supports_building_command(command_type)
    )


def _number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return float(value)


def _validate_building_transform(
    model: dict[str, Any],
    translation: dict[str, float],
    rotation_deg: float,
) -> None:
    site = model.get("site") or {}
    building = model.get("building") or {}
    properties = model.get("properties") or {}
    site_width = _number(site.get("width"))
    site_depth = _number(site.get("depth"))
    footprint_width = _number(properties.get("footprint_width_m") or building.get("footprint_width_m"))
    footprint_depth = _number(properties.get("footprint_depth_m") or building.get("footprint_depth_m"))
    if site_width is None or site_depth is None or footprint_width is None or footprint_depth is None:
        raise ValueError(
            "BUILDING_TRANSFORM_UNDERCONSTRAINED: canonical site width/depth and building footprint dimensions are required"
        )
    if footprint_width > site_width or footprint_depth > site_depth:
        raise ValueError("BUILDING_TRANSFORM_OUTSIDE_SITE: the canonical building footprint exceeds the site bounds")
    if abs(translation["z"]) > 100_000:
        raise ValueError("BUILDING_TRANSFORM_OUTSIDE_COORDINATE_LIMIT: vertical translation exceeds the supported coordinate range")

    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    center_x = (site_width - footprint_width) / 2 + translation["x"] + footprint_width / 2
    center_y = (site_depth - footprint_depth) / 2 + translation["y"] + footprint_depth / 2
    half_x = abs(cosine) * footprint_width / 2 + abs(sine) * footprint_depth / 2
    half_y = abs(sine) * footprint_width / 2 + abs(cosine) * footprint_depth / 2
    if (
        center_x - half_x < -1e-6
        or center_y - half_y < -1e-6
        or center_x + half_x > site_width + 1e-6
        or center_y + half_y > site_depth + 1e-6
    ):
        raise ValueError("BUILDING_TRANSFORM_OUTSIDE_SITE: transformed building footprint must remain inside the site")




def _validate_space_anchor(
    model: dict[str, Any],
    element: dict[str, Any],
    translation: dict[str, float],
) -> None:
    building = model.get("building") or {}
    properties = model.get("properties") or {}
    width = _number(properties.get("footprint_width_m") or building.get("footprint_width_m"))
    depth = _number(properties.get("footprint_depth_m") or building.get("footprint_depth_m"))
    if width is None or depth is None:
        raise ValueError("SPACE_MOVE_UNDERCONSTRAINED: canonical building footprint dimensions are required")

    semantic = model.get("semantic_model") or {}
    relationships = semantic.get("relationships") or []
    storey_ids = {
        relationship.get("source_id")
        for relationship in relationships
        if relationship.get("target_id") == element.get("id")
        and relationship.get("relationship_type") == "contains_space"
    }
    storey = next(
        (item for item in semantic.get("elements", []) if item.get("id") in storey_ids),
        None,
    )
    if storey is None:
        raise ValueError("SPACE_MOVE_UNDERCONSTRAINED: a canonical storey placement is required")
    level_item = (storey.get("properties") or {}).get("level_number") or {}
    level_number = level_item.get("value") if isinstance(level_item, dict) else None
    level = next(
        (row for row in model.get("levels", []) if int(row.get("level_number", -1)) == int(level_number or -1)),
        None,
    )
    if level is None:
        raise ValueError("SPACE_MOVE_UNDERCONSTRAINED: the containing storey row is missing")
    height = _number(level.get("floor_to_floor_height"))
    if height is None or height <= 0:
        raise ValueError("SPACE_MOVE_UNDERCONSTRAINED: the containing storey's height is required")
    if (
        translation["x"] < -1e-6 or translation["y"] < -1e-6
        or translation["x"] > width + 1e-6 or translation["y"] > depth + 1e-6
        or translation["z"] < -1e-6 or translation["z"] > height + 1e-6
    ):
        raise ValueError("SPACE_MOVE_OUTSIDE_BUILDING: space anchor must remain inside its building footprint and storey height")


def apply_geometry_command(
    model: dict[str, Any],
    state: dict[str, Any],
    command: CommandEnvelope,
    actor_id: str,
) -> dict[str, Any]:
    """Apply a supported building transform to canonical World Model state."""
    if command.type not in GEOMETRY_COMMAND_TYPES:
        raise ValueError(f"geometry adapter does not handle command: {command.type}")

    element_id = command.payload.get("element_id")
    if not isinstance(element_id, str) or not element_id.strip():
        raise ValueError("element_id must be a non-empty string")
    semantic = model.get("semantic_model") or {}
    element = next(
        (item for item in semantic.get("elements", []) if item.get("id") == element_id),
        None,
    )
    expected_type = "Space" if command.type == "MoveSpace" else "Building"
    if element is None or element.get("element_type") != expected_type:
        raise ValueError(f"COMMAND_TARGET_TYPE_MISMATCH: expected {expected_type}")

    properties = element.get("properties") or {}
    translation_item = properties.get("translation_m") or {}
    current_translation = translation_item.get("value") if isinstance(translation_item, dict) else None
    current_translation = current_translation if isinstance(current_translation, dict) else {"x": 0.0, "y": 0.0, "z": 0.0}

    if command.type == "MoveSpace":
        delta = command.payload["translation_m"]
        target_translation = {
            axis: float(current_translation.get(axis, 0.0)) + float(delta[axis])
            for axis in ("x", "y", "z")
        }
        _validate_space_anchor(model, element, target_translation)
        return edit_property(model, state, element_id, "translation_m", target_translation, actor_id, command.reason)

    rotation_item = properties.get("rotation_deg") or {}
    current_rotation = _number(rotation_item) or 0.0

    if command.type == "MoveBuilding":
        delta = command.payload["translation_m"]
        target_translation = {
            axis: float(current_translation.get(axis, 0.0)) + float(delta[axis])
            for axis in ("x", "y", "z")
        }
        target_rotation = current_rotation
        property_name = "translation_m"
        target_value: Any = target_translation
    else:
        target_translation = {
            axis: float(current_translation.get(axis, 0.0))
            for axis in ("x", "y", "z")
        }
        target_rotation = (current_rotation + float(command.payload["angle_deg"])) % 360.0
        property_name = "rotation_deg"
        target_value = target_rotation

    _validate_building_transform(model, target_translation, target_rotation)
    return edit_property(model, state, element_id, property_name, target_value, actor_id, command.reason)
