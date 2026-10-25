from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contract import canonical_payload
from .schemas import CommandEnvelope


@dataclass(frozen=True)
class CommandChange:
    field: str
    before: Any
    after: Any


def explain_command(command: CommandEnvelope) -> tuple[CommandChange, ...]:
    """Return deterministic, model-independent changes implied by a command."""
    payload = canonical_payload(command)
    if command.type in {"MoveBuilding", "MoveSpace"}:
        return (CommandChange("translation_m", None, payload["translation_m"]),)
    if command.type == "RotateBuilding":
        return (CommandChange("angle_deg", None, payload["angle_deg"]),)
    if command.type in {"ResizeSpace", "SetProgramArea"}:
        return (CommandChange("area_m2", None, payload["area_m2"]),)
    if command.type == "ChangeSetback":
        return (CommandChange("setback_m", None, payload["setback_m"]),)
    return tuple(CommandChange(key, None, payload[key]) for key in sorted(payload))
