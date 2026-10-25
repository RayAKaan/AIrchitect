from __future__ import annotations

from .schemas import CommandEnvelope, CommandPreview
from .service import validate_command


def preview_command(command: CommandEnvelope) -> CommandPreview:
    validation = validate_command(command)
    return CommandPreview(
        command_id=command.command_id,
        command_type=command.type,
        accepted=validation.valid,
        base_revision_hash=command.base_revision_hash,
        impact=[],
        warnings=validation.warnings,
        validation_errors=validation.errors,
    )
