from __future__ import annotations

import hashlib

from app.domains.commands.builtins import registry
from app.domains.commands.schemas import CommandEnvelope

from .proposals import AIProposal, validate_ai_proposal


def _idempotency_key(proposal: AIProposal, command_id: str) -> str:
    material = "|".join((proposal.proposal_id, command_id, proposal.base_revision_hash))
    return "ai-" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def compile_proposal_commands(proposal: AIProposal) -> tuple[CommandEnvelope, ...]:
    """Compile an AI proposal into preview-only commands accepted by the canonical registry."""

    validation = validate_ai_proposal(proposal)
    if not validation.valid:
        raise ValueError("; ".join(validation.errors))

    commands = tuple(
        CommandEnvelope(
            command_id=command.command_id,
            type=command.command_type,
            schema_version=1,
            project_id=proposal.project_id,
            version_id=proposal.version_id,
            base_revision_hash=proposal.base_revision_hash,
            idempotency_key=_idempotency_key(proposal, command.command_id),
            payload=command.payload,
            mode="preview",
            reason=command.reason,
        )
        for command in proposal.commands
    )
    unsupported = [
        f"{command.type}@{command.schema_version}"
        for command in commands
        if registry.get(command.type, command.schema_version) is None
    ]
    if unsupported:
        raise ValueError(f"AI proposal contains unsupported commands: {unsupported}")

    invalid = [
        error
        for command in commands
        for error in registry.validate(command).errors
    ]
    if invalid:
        raise ValueError("; ".join(invalid))
    return commands
