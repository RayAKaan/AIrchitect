from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.semantic_model.editing import check_expected_revision, load_editable_model, persist_designer_mutation

from .executor import execute_semantic_command
from .intent_contract import contract_for
from .intent_parser import parse_intent
from .preview import preview_command
from .schemas import CommandEnvelope, CommandPreview, CommandResult

router = APIRouter(tags=["commands"])


class IntentPreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class IntentPreviewResponse(BaseModel):
    command_type: str | None
    payload: dict[str, Any]
    confidence: float
    missing_fields: list[str]
    ambiguous: bool
    executable: bool
    reason: str | None = None


@router.post("/commands/intent-preview", response_model=IntentPreviewResponse)
async def intent_preview(body: IntentPreviewRequest, user: User = Depends(current_user)) -> IntentPreviewResponse:
    """Expose intent interpretation without constructing or committing a command."""
    proposal = parse_intent(body.text)
    contract = contract_for(proposal)
    return IntentPreviewResponse(
        command_type=contract.command_type,
        payload=contract.payload,
        confidence=proposal.confidence,
        missing_fields=list(contract.missing_fields),
        ambiguous=proposal.ambiguous,
        executable=contract.executable,
        reason=contract.reason,
    )


@router.post("/commands/preview", response_model=CommandPreview)
async def preview(body: CommandEnvelope, user: User = Depends(current_user)) -> CommandPreview:
    return preview_command(body)


@router.post("/commands/commit", response_model=CommandResult)
async def commit(body: CommandEnvelope, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> CommandResult:
    if body.mode != "commit":
        raise ValueError("command mode must be commit")
    project, version, world, model, state = await load_editable_model(session, body.project_id, body.version_id, user)
    if world.model_hash != body.base_revision_hash:
        raise ValueError("STALE_WORLD_MODEL")
    await check_expected_revision(version, version.revision_number)
    result = execute_semantic_command(model, state, body, user.id, world.model_hash)
    persist_event = state["history"][-1].get("result") if state.get("history") else None
    world = await persist_designer_mutation(
        session, project=project, version=version, user=user, model=model,
        action="COMMAND", event=persist_event,
    )
    result.revision_hash = world.model_hash
    return result
