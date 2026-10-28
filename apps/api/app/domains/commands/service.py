from __future__ import annotations

from .architectural_constraints import validate_architectural_constraints
from .builtins import registry
from .contract import validate_payload_contract
from .schemas import CommandEnvelope, CommandValidationResult
from .semantic_adapter import supports_semantic_command


def validate_command(command: CommandEnvelope) -> CommandValidationResult:
    """Validate command identity, payload contracts, and mathematical invariants."""
    contract = validate_payload_contract(command)
    if not contract.valid:
        return contract
    constraint_errors = validate_architectural_constraints(command)
    if constraint_errors:
        return CommandValidationResult(valid=False, errors=constraint_errors)
    result = registry.validate(command)
    if not result.valid:
        return result
    if not supports_semantic_command(command.type):
        return CommandValidationResult(
            valid=False,
            errors=[f"COMMAND_NOT_EXECUTABLE: {command.type} has no canonical mutation adapter"],
        )
    return result
