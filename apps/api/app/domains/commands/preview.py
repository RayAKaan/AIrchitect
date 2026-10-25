from __future__ import annotations

from .impact import impact_for
from .schemas import CommandEnvelope, CommandPreview
from .service import validate_command


def preview_command(command: CommandEnvelope) -> CommandPreview:
    validation = validate_command(command)
    return CommandPreview(
        command_id=command.command_id,
        command_type=command.type,
        accepted=validation.valid,
        base_revision_hash=command.base_revision_hash,
        impact=impact_for(command) if validation.valid else [],
        warnings=validation.warnings,
        validation_errors=validation.errors,
    )
