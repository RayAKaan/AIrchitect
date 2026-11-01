from __future__ import annotations

from typing import Any

from app.domains.semantic_model.editing import edit_property

from .schemas import CommandEnvelope


def supports_planning_command(command_type: str) -> bool:
    return command_type == "ChangeSetback"


def apply_planning_command(
    model: dict[str, Any],
    state: dict[str, Any],
    command: CommandEnvelope,
    actor_id: str,
) -> dict[str, Any]:
    """Persist a user-authored planning design parameter without asserting legal authority."""
    if command.type != "ChangeSetback":
        raise ValueError(f"planning adapter does not handle command: {command.type}")
    semantic = model.get("semantic_model") or {}
    site = next(
        (item for item in semantic.get("elements", []) if item.get("element_type") == "Site"),
        None,
    )
    if site is None:
        raise ValueError("SEMANTIC_SITE_NOT_FOUND: canonical Site element is required")
    return edit_property(
        model,
        state,
        site["id"],
        "setback_m",
        float(command.payload["setback_m"]),
        actor_id,
        command.reason,
    )
