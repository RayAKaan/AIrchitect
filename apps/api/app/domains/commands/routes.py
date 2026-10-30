from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactVersion, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.semantic_model.editing import check_expected_revision, load_editable_model, persist_designer_mutation

from .artifact_lifecycle import invalidate_and_enqueue
from .executor import execute_semantic_command
from .plan_execution import execute_plan
from .impact import impact_for
from .idempotency import find_replay
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


class PlanCommitRequest(PlanPreviewRequest):
    fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class PlanCommitResponse(BaseModel):
    plan_id: str
    status: Literal["committed", "replayed"]
    fingerprint: str
    revision_hash: str
    command_results: list[CommandResult]
    impact_groups: list[str]
    invalidated_artifact_ids: list[str]


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


@router.post("/commands/plan-commit", response_model=PlanCommitResponse)
async def commit_plan(
    body: PlanCommitRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PlanCommitResponse:
    """Commit a reviewed command plan as one canonical revision and transaction."""
    preview = preview_sequential_plan(body.plan_id, body.commands)
    if not preview.executable or preview.fingerprint is None:
        raise ValueError("INVALID_COMMAND_PLAN: " + "; ".join(preview.validation_errors))
    if preview.fingerprint != body.fingerprint:
        raise ValueError("PLAN_FINGERPRINT_MISMATCH")
    if any(command.mode != "commit" for command in body.commands):
        raise ValueError("all plan commands must use commit mode")

    first = body.commands[0]
    project, version, world, model, state = await load_editable_model(
        session, first.project_id, first.version_id, user
    )
    replay_events = [find_replay(state, command) for command in body.commands]
    replayed = [event is not None for event in replay_events]
    if any(replayed) and not all(replayed):
        raise ValueError("PARTIAL_PLAN_REPLAY: all commands must replay or all must be new")
    if all(replayed):
        replay_results = [
            CommandResult(**{
                **event["result"],
                "status": "replayed",
                "canonical_mutation": False,
                "revision_hash": world.model_hash,
            })
            for event in replay_events
            if event is not None
        ]
        return PlanCommitResponse(
            plan_id=body.plan_id,
            status="replayed",
            fingerprint=preview.fingerprint,
            revision_hash=world.model_hash,
            command_results=replay_results,
            impact_groups=[],
            invalidated_artifact_ids=[],
        )
    if world.model_hash != preview.plan.base_revision_hash:
        raise ValueError("STALE_WORLD_MODEL")
    await check_expected_revision(version, version.revision_number)

    execution = execute_plan(model, state, preview.plan, body.commands, user.id, world.model_hash)
    results = list(execution.results)
    replayed = [result.status == "replayed" for result in results]
    if any(replayed) and not all(replayed):
        raise ValueError("PARTIAL_PLAN_REPLAY: all commands must replay or all must be new")
    if all(replayed):
        return PlanCommitResponse(
            plan_id=body.plan_id,
            status="replayed",
            fingerprint=preview.fingerprint,
            revision_hash=world.model_hash,
            command_results=results,
            impact_groups=[],
            invalidated_artifact_ids=[],
        )

    # Batch execution deep-copies model and state independently; reconnect the
    # authoritative designer state before the single persistence operation.
    execution.model["designer_state"] = execution.state
    persist_event = execution.state["history"][-1].get("result") if execution.state.get("history") else None
    world = await persist_designer_mutation(
        session,
        project=project,
        version=version,
        user=user,
        model=execution.model,
        action="COMMAND_PLAN",
        event=persist_event,
        commit=False,
    )
    invalidated_artifact_ids = await invalidate_and_enqueue(
        session,
        project=project,
        version=version,
        source_revision_hash=world.model_hash,
        groups=preview.impact_groups,
    )
    await session.commit()
    for result in results:
        result.revision_hash = world.model_hash
    return PlanCommitResponse(
        plan_id=body.plan_id,
        status="committed",
        fingerprint=preview.fingerprint,
        revision_hash=world.model_hash,
        command_results=results,
        impact_groups=list(preview.impact_groups),
        invalidated_artifact_ids=list(invalidated_artifact_ids),
    )

@router.post("/commands/commit", response_model=CommandResult)
async def commit(body: CommandEnvelope, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> CommandResult:
    if body.mode != "commit":
        raise ValueError("command mode must be commit")
    project, version, world, model, state = await load_editable_model(session, body.project_id, body.version_id, user)
    await check_expected_revision(version, version.revision_number)
    replay = find_replay(state, body)
    if replay is not None:
        return CommandResult(**{
            **replay["result"],
            "status": "replayed",
            "canonical_mutation": False,
            "revision_hash": world.model_hash,
        })
    if world.model_hash != body.base_revision_hash:
        raise ValueError("STALE_WORLD_MODEL")
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
    await invalidate_and_enqueue(
        session, project=project, version=version, source_revision_hash=world.model_hash, groups=groups
    )
    await session.commit()
    result.revision_hash = world.model_hash
    return result
