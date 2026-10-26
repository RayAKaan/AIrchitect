from __future__ import annotations

from app.domains.commands.plan_preview import PlanPreview, preview_sequential_plan

from .proposal_compiler import compile_proposal_commands
from .proposals import AIProposal, validate_ai_proposal


def preview_proposal_plan(proposal: AIProposal) -> PlanPreview:
    """Project a validated AI proposal through the existing deterministic plan preview."""

    validation = validate_ai_proposal(proposal)
    if not validation.valid:
        raise ValueError("; ".join(validation.errors))
    commands = compile_proposal_commands(proposal)
    return preview_sequential_plan(proposal.proposal_id, commands)
