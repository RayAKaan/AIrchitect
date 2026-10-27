from __future__ import annotations

from dataclasses import dataclass

from app.domains.ai.approval import issue_approval_token
from app.domains.ai.copilot_impact import explain_impact_groups
from app.domains.ai.copilot_plan import preview_proposal_plan
from app.domains.ai.proposal_compiler import compile_proposal_commands
from app.domains.ai.proposals import AIProposal


@dataclass(frozen=True)
class CopilotLoop:
    proposal: AIProposal
    commands: tuple[dict, ...]
    execution_order: tuple[str, ...]
    impact_groups: tuple[dict, ...]
    plan_fingerprint: str
    approval_token: str


def assemble_copilot_loop(proposal: AIProposal) -> CopilotLoop:
    """Build the complete non-mutating Copilot handoff in one deterministic boundary."""
    preview = preview_proposal_plan(proposal)
    if not preview.executable or not preview.fingerprint:
        raise ValueError("COPILOT_PROPOSAL_NOT_EXECUTABLE")

    impacts = explain_impact_groups(list(preview.impact_groups))
    token = issue_approval_token(proposal, preview.fingerprint)
    commands = compile_proposal_commands(proposal)
    return CopilotLoop(
        proposal=proposal,
        commands=tuple(
            {
                "command_id": command.command_id,
                "type": command.type,
                "schema_version": command.schema_version,
                "payload": command.payload,
            }
            for command in commands
        ),
        execution_order=tuple(preview.execution_order),
        impact_groups=tuple(
            {
                "group": item.group,
                "artifact_type": item.artifact_type,
                "description": item.description,
                "regeneration_required": item.regeneration_required,
            }
            for item in impacts
        ),
        plan_fingerprint=preview.fingerprint,
        approval_token=token,
    )
