from __future__ import annotations

from .builtins import registry
from .contract import validate_payload_contract
from .schemas import CommandEnvelope, CommandValidationResult


def validate_command(command: CommandEnvelope) -> CommandValidationResult:
    """Validate command identity and payload without touching canonical state."""
    contract = validate_payload_contract(command)
    if not contract.valid:
        return contract
    return registry.validate(command)
