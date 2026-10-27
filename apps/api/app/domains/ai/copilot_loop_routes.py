from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import current_user
from app.domains.ai.copilot_loop import assemble_copilot_loop
from app.domains.ai.proposals import AIProposal

router = APIRouter(tags=["ai-copilot"])


@router.post("/projects/{project_id}/ai/copilot/loop")
async def copilot_loop(
    project_id: str,
    proposal: AIProposal,
    user=Depends(current_user),
) -> dict:
    """Return the complete preview/impact/approval handoff without mutating canonical state."""
    if proposal.project_id != project_id:
        raise HTTPException(status_code=422, detail="proposal project does not match route project")
    try:
        loop = assemble_copilot_loop(proposal)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "proposal": loop.proposal.model_dump(mode="json"),
        "commands": list(loop.commands),
        "execution_order": list(loop.execution_order),
        "impact_groups": list(loop.impact_groups),
        "plan_fingerprint": loop.plan_fingerprint,
        "approval_token": loop.approval_token,
        "requires_confirmation": True,
        "canonical_state_mutated": False,
    }
