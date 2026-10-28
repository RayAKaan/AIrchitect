from __future__ import annotations

from .registry import CommandDefinition, CommandRegistry, require_payload_keys
from .schemas import CommandEnvelope, CommandValidationResult


COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("SetSiteBoundary", ("site_id", "boundary")),
    ("MoveBuilding", ("element_id", "translation_m")),
    ("RotateBuilding", ("element_id", "angle_deg")),
    ("ChangeSetback", ("setback_m",)),
    ("AddLevel", ("building_id", "elevation_m")),
    ("ResizeSpace", ("element_id", "area_m2")),
    ("MoveSpace", ("element_id", "translation_m")),
    ("SetProgramArea", ("space_type", "area_m2")),
    ("LockEntity", ("element_id",)),
    ("Undo", ()),
    ("Redo", ()),
)


def _validate_reason(command: CommandEnvelope) -> CommandValidationResult:
    result = require_payload_keys(*dict(COMMANDS)[command.type])(command)
    if not result.valid:
        return result
    if command.mode == "commit" and not command.reason.strip():
        return CommandValidationResult(valid=False, errors=["commit commands require a reason"])
    return result


def build_registry() -> CommandRegistry:
    registry = CommandRegistry()
    for name, _ in COMMANDS:
        registry.register(CommandDefinition(name=name, schema_version=1, validator=_validate_reason))
    return registry


registry = build_registry()
