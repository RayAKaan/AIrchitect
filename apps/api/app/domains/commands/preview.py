from __future__ import annotations

from .impact import impact_for
from .schemas import CommandEnvelope, CommandPreview
from .service import validate_command
from .semantic_adapter import supports_semantic_command


def preview_command(command: CommandEnvelope) -> CommandPreview:
    validation = validate_command(command)
    supported = supports_semantic_command(command.type)
    blockers = (
        []
        if supported
        else [f"COMMAND_NOT_EXECUTABLE: {command.type} has no canonical mutation adapter"]
    )
    return CommandPreview(
        command_id=command.command_id,
        command_type=command.type,
        accepted=validation.valid,
        executable=validation.valid and supported,
        execution_blockers=blockers if validation.valid else [],
        base_revision_hash=command.base_revision_hash,
        impact=impact_for(command) if validation.valid else [],
        warnings=validation.warnings,
        validation_errors=validation.errors,
    )
