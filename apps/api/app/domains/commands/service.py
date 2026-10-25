from __future__ import annotations

from .builtins import registry
from .schemas import CommandEnvelope, CommandValidationResult


def validate_command(command: CommandEnvelope) -> CommandValidationResult:
    """Validate command type and payload without touching canonical state."""
    return registry.validate(command)
