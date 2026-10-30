from __future__ import annotations

import math
from typing import Any

from app.domains.semantic_model.editing import edit_property

from .schemas import CommandEnvelope
from .semantic_adapter import supports_semantic_command
from .program_adapter import supports_program_command


GEOMETRY_COMMAND_TYPES = frozenset({"MoveBuilding", "RotateBuilding"})


def supports_geometry_command(command_type: str) -> bool:
    return command_type in GEOMETRY_COMMAND_TYPES


def supports_command(command_type: str) -> bool:
    """Return whether a command has an executable canonical mutation adapter."""
    return (
        supports_semantic_command(command_type)
        or command_type in GEOMETRY_COMMAND_TYPES
        or supports_program_command(command_type)
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
    if element is None or element.get("element_type") != "Building":
        raise ValueError("COMMAND_TARGET_TYPE_MISMATCH: expected Building")

    properties = element.get("properties") or {}
    translation_item = properties.get("translation_m") or {}
    current_translation = translation_item.get("value") if isinstance(translation_item, dict) else None
    current_translation = current_translation if isinstance(current_translation, dict) else {"x": 0.0, "y": 0.0, "z": 0.0}
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
