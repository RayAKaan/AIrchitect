from __future__ import annotations

from .intent_contract import contract_for
from .intent_parser import IntentProposal
from .schemas import CommandEnvelope


def proposal_to_preview_command(
    proposal: IntentProposal,
    *,
    project_id: str,
    version_id: str,
    base_revision_hash: str,
    command_id: str,
    idempotency_key: str,
    reason: str,
) -> CommandEnvelope:
    """Convert only a complete intent into the canonical preview command envelope."""
    contract = contract_for(proposal)
    if not contract.executable:
        raise ValueError(contract.reason or "intent is not executable")
    payload = {key: value for key, value in contract.payload.items() if key != "target_name"}
    return CommandEnvelope(
        command_id=command_id,
        type=contract.command_type or "",
        schema_version=1,
        project_id=project_id,
        version_id=version_id,
        base_revision_hash=base_revision_hash,
        idempotency_key=idempotency_key,
        payload=payload,
        mode="preview",
        reason=reason.strip()[:500],
    )
