from __future__ import annotations

from dataclasses import dataclass

from .intent_parser import IntentProposal
from .requirements import requirements_for
from .geometry_adapter import supports_command


@dataclass(frozen=True)
class IntentContract:
    command_type: str | None
    payload: dict[str, object]
    missing_fields: tuple[str, ...]
    executable: bool
    reason: str | None = None


def contract_for(proposal: IntentProposal) -> IntentContract:
    if proposal.ambiguous or proposal.command_type is None:
        return IntentContract(None, {}, (), False, "intent is ambiguous or unsupported")
    requirement = requirements_for(proposal.command_type)
    if requirement is None:
        return IntentContract(proposal.command_type, dict(proposal.payload), (), False, "command is not registered")
    missing = tuple(field for field in requirement.required_fields if field not in proposal.payload)
    supported = supports_command(proposal.command_type)
    if not supported:
        reason = "command has no canonical mutation adapter yet"
    elif missing:
        reason = "required command fields are missing"
    else:
        reason = None
    return IntentContract(
        proposal.command_type,
        dict(proposal.payload),
        missing,
        supported and not missing,
        reason,
    )
