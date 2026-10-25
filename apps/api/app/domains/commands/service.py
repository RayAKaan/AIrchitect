from __future__ import annotations

from .architectural_constraints import validate_architectural_constraints
from .builtins import registry
from .contract import validate_payload_contract
from .schemas import CommandEnvelope, CommandValidationResult


def validate_command(command: CommandEnvelope) -> CommandValidationResult:
    """Validate command identity, payload contracts, and mathematical invariants."""
    contract = validate_payload_contract(command)
    if not contract.valid:
        return contract
    constraint_errors = validate_architectural_constraints(command)
    if constraint_errors:
        return CommandValidationResult(valid=False, errors=constraint_errors)
    return registry.validate(command)
