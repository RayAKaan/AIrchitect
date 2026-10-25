from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
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
from .target_resolution import resolve_target

router = APIRouter(tags=["commands"])


class IntentPreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    project_id: str | None = Field(default=None, min_length=1, max_length=64)
    version_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def paired_context(self) -> "IntentPreviewRequest":
        if (self.project_id is None) != (self.version_id is None):
            raise ValueError("project_id and version_id must be provided together")
        return self


class IntentPreviewResponse(BaseModel):
    command_type: str | None
    payload: dict[str, Any]
    confidence: float
    missing_fields: list[str]
    ambiguous: bool
    executable: bool
    reason: str | None = None
    model_revision_hash: str | None = None


_EXPECTED_TYPES = {
    "MoveBuilding": "Building",
    "RotateBuilding": "Building",
    "ResizeSpace": "Space",
    "MoveSpace": "Space",
}


@router.post("/commands/intent-preview", response_model=IntentPreviewResponse)
async def intent_preview(body: IntentPreviewRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> IntentPreviewResponse:
    """Expose deterministic intent interpretation without mutating canonical state."""
    proposal = parse_intent(body.text)
    payload = dict(proposal.payload)
    revision_hash: str | None = None
    if body.project_id is not None and body.version_id is not None and proposal.command_type in _EXPECTED_TYPES:
        _, _, world, model, _ = await load_editable_model(session, body.project_id, body.version_id, user)
        revision_hash = world.model_hash
        target_name = payload.get("target_name")
        if isinstance(target_name, str) and "element_id" not in payload:
            resolution = resolve_target(model, name=target_name, expected_type=_EXPECTED_TYPES[proposal.command_type])
            if resolution.ambiguous:
                proposal = proposal.__class__(None, {}, 0.0, (), True)
            elif resolution.element_id is not None:
                payload["element_id"] = resolution.element_id
    proposal = proposal.__class__(proposal.command_type, payload, proposal.confidence, proposal.missing_fields, proposal.ambiguous)
    contract = contract_for(proposal)
    return IntentPreviewResponse(
        command_type=contract.command_type,
        payload=contract.payload,
        confidence=proposal.confidence,
        missing_fields=list(contract.missing_fields),
        ambiguous=proposal.ambiguous,
        executable=contract.executable,
        reason=contract.reason,
        model_revision_hash=revision_hash,
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
    world = await persist_designer_mutation(session, project=project, version=version, user=user, model=model, action="COMMAND", event=persist_event)
    result.revision_hash = world.model_hash
    return result
