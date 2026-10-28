from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactVersion, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.semantic_model.editing import check_expected_revision, load_editable_model, persist_designer_mutation

from .artifact_invalidation import ArtifactInvalidationService
from .executor import execute_semantic_command
from .impact import impact_for
from .intent_contract import contract_for
from .intent_parser import parse_intent
from .plan_preview import preview_sequential_plan
from .preview import preview_command
from .regeneration_executor import RegenerationHandlerRegistry
from .regeneration_queue import RegenerationQueue
from .regeneration_repository import RegenerationStateRepository
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


class PlanPreviewRequest(BaseModel):
    plan_id: str = Field(min_length=1, max_length=128)
    commands: list[CommandEnvelope] = Field(min_length=1, max_length=100)


class PlanPreviewResponse(BaseModel):
    plan_id: str
    project_id: str
    version_id: str
    base_revision_hash: str
    executable: bool
    command_ids: list[str]
    execution_order: list[str]
    impact_groups: list[str]
    fingerprint: str | None
    validation_errors: list[str]
    warnings: list[str]


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


@router.post("/commands/plan-preview", response_model=PlanPreviewResponse)
async def plan_preview(body: PlanPreviewRequest, user: User = Depends(current_user)) -> PlanPreviewResponse:
    """Project a deterministic sequential command plan without mutating canonical state."""
    preview = preview_sequential_plan(body.plan_id, body.commands)
    return PlanPreviewResponse(
        plan_id=preview.plan.plan_id,
        project_id=preview.plan.project_id,
        version_id=preview.plan.version_id,
        base_revision_hash=preview.plan.base_revision_hash,
        executable=preview.executable,
        command_ids=list(preview.command_ids),
        execution_order=list(preview.execution_order),
        impact_groups=list(preview.impact_groups),
        fingerprint=preview.fingerprint,
        validation_errors=list(preview.validation_errors),
        warnings=list(preview.warnings),
    )


@router.post("/commands/commit", response_model=CommandResult)
async def commit(body: CommandEnvelope, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> CommandResult:
    if body.mode != "commit":
        raise ValueError("command mode must be commit")
    project, version, world, model, state = await load_editable_model(session, body.project_id, body.version_id, user)
    if world.model_hash != body.base_revision_hash:
        raise ValueError("STALE_WORLD_MODEL")
    await check_expected_revision(version, version.revision_number)
    result = execute_semantic_command(model, state, body, user.id, world.model_hash)

    # Persist the fully normalized canonical model without committing yet. The
    # returned row hash is the authoritative source revision for invalidation.
    # Keep the revision, audit event, stale propagation, and queue entries in one
    # transaction so a failure cannot leave only part of the command committed.
    persist_event = state["history"][-1].get("result") if state.get("history") else None
    world = await persist_designer_mutation(
        session,
        project=project,
        version=version,
        user=user,
        model=model,
        action="COMMAND",
        event=persist_event,
        commit=False,
    )
    groups = impact_for(body)
    invalidated_artifact_ids = await ArtifactInvalidationService().invalidate_groups(
        session,
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        source_revision_hash=world.model_hash,
        groups=groups,
    )
    states = RegenerationStateRepository()
    queue = RegenerationQueue(states)
    if invalidated_artifact_ids:
        artifact_result = await session.scalars(
            select(ArtifactVersion)
            .where(ArtifactVersion.id.in_(invalidated_artifact_ids))
            .order_by(ArtifactVersion.id)
        )
        handlers = RegenerationHandlerRegistry()
        for artifact in artifact_result.all():
            # Unsupported artifact types stay stale and block release; do not
            # enqueue work that has no deterministic implementation.
            if not handlers.supports(artifact.artifact_type):
                continue
            regeneration_state = await states.get_for_update(session, artifact.id)
            if regeneration_state is None:
                raise ValueError("artifact invalidation created no regeneration state")
            await queue.enqueue(session, regeneration_state)

    await session.commit()
    result.revision_hash = world.model_hash
    return result
