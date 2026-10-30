from __future__ import annotations

import math
from typing import Any

from app.domains.semantic_model.editing import edit_property

from .schemas import CommandEnvelope
from .semantic_adapter import supports_semantic_command


GEOMETRY_COMMAND_TYPES = frozenset({"MoveBuilding"})


def supports_command(command_type: str) -> bool:
    """Return whether a command has an executable canonical mutation adapter."""
    return supports_semantic_command(command_type) or command_type in GEOMETRY_COMMAND_TYPES


def _number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return float(value)


def _validate_building_translation(model: dict[str, Any], translation: dict[str, float]) -> None:
    site = model.get("site") or {}
    building = model.get("building") or {}
    properties = model.get("properties") or {}
    site_width = _number(site.get("width"))
    site_depth = _number(site.get("depth"))
    footprint_width = _number(properties.get("footprint_width_m") or building.get("footprint_width_m"))
    footprint_depth = _number(properties.get("footprint_depth_m") or building.get("footprint_depth_m"))
    if site_width is None or site_depth is None or footprint_width is None or footprint_depth is None:
        raise ValueError(
            "BUILDING_MOVE_UNDERCONSTRAINED: canonical site width/depth and building footprint dimensions are required"
        )
    if footprint_width > site_width or footprint_depth > site_depth:
        raise ValueError("BUILDING_MOVE_OUTSIDE_SITE: the canonical building footprint exceeds the site bounds")

    if abs(translation["z"]) > 100_000:
        raise ValueError("BUILDING_MOVE_OUTSIDE_COORDINATE_LIMIT: vertical translation exceeds the supported coordinate range")

    origin_x = (site_width - footprint_width) / 2 + translation["x"]
    origin_y = (site_depth - footprint_depth) / 2 + translation["y"]
    if (
        origin_x < -1e-6
        or origin_y < -1e-6
        or origin_x + footprint_width > site_width + 1e-6
        or origin_y + footprint_depth > site_depth + 1e-6
    ):
        raise ValueError("BUILDING_MOVE_OUTSIDE_SITE: translated building footprint must remain inside the site")


def apply_geometry_command(
    model: dict[str, Any],
    state: dict[str, Any],
    command: CommandEnvelope,
    actor_id: str,
) -> dict[str, Any]:
    """Apply a geometry command to canonical World Model state with designer history."""
    if command.type != "MoveBuilding":
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

    current_item = (element.get("properties") or {}).get("translation_m") or {}
    current = current_item.get("value") if isinstance(current_item, dict) else None
    current = current if isinstance(current, dict) else {"x": 0.0, "y": 0.0, "z": 0.0}
    delta = command.payload["translation_m"]
    target = {
        axis: float(current.get(axis, 0.0)) + float(delta[axis])
        for axis in ("x", "y", "z")
    }
    _validate_building_translation(model, target)
    return edit_property(model, state, element_id, "translation_m", target, actor_id, command.reason)
