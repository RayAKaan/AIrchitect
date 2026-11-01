from __future__ import annotations

from typing import Any

from app.domains.program.service import CATALOG
from app.domains.semantic_model.editing import edit_property

from .schemas import CommandEnvelope


def supports_program_command(command_type: str) -> bool:
    return command_type == "SetProgramArea"


def apply_program_command(
    model: dict[str, Any],
    state: dict[str, Any],
    command: CommandEnvelope,
    actor_id: str,
) -> dict[str, Any]:
    """Persist a reviewed space-type target without mutating physical spaces."""
    if command.type != "SetProgramArea":
        raise ValueError(f"program adapter does not handle command: {command.type}")

    space_type = command.payload.get("space_type")
    known_space_types = {
        name.lower().replace(" ", "_")
        for catalog in CATALOG.values()
        for name, _, _ in catalog
    }
    if not isinstance(space_type, str) or space_type not in known_space_types:
        raise ValueError("space_type must identify a known program space type")

    semantic = model.get("semantic_model") or {}
    building = next(
        (item for item in semantic.get("elements", []) if item.get("element_type") == "Building"),
        None,
    )
    if building is None:
        raise ValueError("SEMANTIC_BUILDING_NOT_FOUND: canonical Building element is required")

    current_item = (building.get("properties") or {}).get("program_area_targets") or {}
    current_targets = current_item.get("value") if isinstance(current_item, dict) else None
    targets = dict(current_targets) if isinstance(current_targets, dict) else {}
    targets[space_type] = float(command.payload["area_m2"])
    return edit_property(
        model,
        state,
        building["id"],
        "program_area_targets",
        targets,
        actor_id,
        command.reason,
    )
