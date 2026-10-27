from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DecisionRecord, EvidenceNode, ProjectVersion, User
from app.domains.ai.approval import verify_approval_token
from app.domains.ai.copilot_plan import preview_proposal_plan
from app.domains.ai.proposal_compiler import compile_proposal_commands
from app.domains.ai.proposals import AIProposal, validate_ai_proposal, validate_proposal_evidence
from app.domains.commands.artifact_invalidation import ArtifactInvalidationService
from app.domains.commands.batch import execute_command_batch
from app.domains.commands.regeneration_queue import RegenerationQueue
from app.domains.commands.regeneration_repository import RegenerationStateRepository
from app.domains.lifecycle.service import canonical_hash
from app.domains.semantic_model.editing import (
    check_expected_revision,
    load_editable_model,
    persist_designer_mutation,
)


async def commit_approved_proposal(
    session: AsyncSession,
    *,
    proposal: AIProposal,
    approval_token: str,
    user: User,
) -> tuple[ProjectVersion, tuple[Any, ...], str]:
    """Commit an approved AI proposal through the canonical command boundary."""

    validation = validate_ai_proposal(proposal)
    if not validation.valid:
        raise ValueError("; ".join(validation.errors))

    claims = verify_approval_token(approval_token)
    bindings = (
        ("proposal_id", proposal.proposal_id),
        ("project_id", proposal.project_id),
        ("version_id", proposal.version_id),
        ("base_revision_hash", proposal.base_revision_hash),
    )
    if any(getattr(claims, field) != expected for field, expected in bindings):
        raise ValueError("APPROVAL_BINDING_MISMATCH")
    if claims.proposal_hash != canonical_hash(proposal.model_dump(mode="json")):
        raise ValueError("APPROVAL_BINDING_MISMATCH")

    project, version, world, model, state = await load_editable_model(
        session,
        proposal.project_id,
        proposal.version_id,
        user,
    )
    if world.model_hash != proposal.base_revision_hash:
        raise ValueError("STALE_WORLD_MODEL")
    await check_expected_revision(version, version.revision_number)

    evidence_ids = set(
        (
            await session.scalars(
                select(EvidenceNode.id).where(
                    EvidenceNode.project_id == project.id,
                    EvidenceNode.project_version_id == version.id,
                )
            )
        ).all()
    )
    evidence_validation = validate_proposal_evidence(proposal, evidence_ids)
    if not evidence_validation.valid:
        raise ValueError("; ".join(evidence_validation.errors))

    plan = preview_proposal_plan(proposal)
    if not plan.executable or not plan.fingerprint:
        raise ValueError("COPILOT_PLAN_NOT_EXECUTABLE")
    if claims.plan_fingerprint != plan.fingerprint:
        raise ValueError("APPROVAL_BINDING_MISMATCH")

    preview_commands = compile_proposal_commands(proposal)
    commands = tuple(command.model_copy(update={"mode": "commit"}) for command in preview_commands)
    execution = execute_command_batch(model, state, commands, user.id, world.model_hash)
    next_revision_hash = canonical_hash(execution.model)

    invalidated_artifact_ids = await ArtifactInvalidationService().invalidate_groups(
        session,
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        source_revision_hash=next_revision_hash,
        groups=plan.impact_groups,
    )

    states = RegenerationStateRepository()
    queue = RegenerationQueue(states)
    for artifact_id in invalidated_artifact_ids:
        regeneration_state = await states.get_for_update(session, artifact_id)
        if regeneration_state is None:
            raise ValueError("artifact invalidation created no regeneration state")
        await queue.enqueue(session, regeneration_state)

    last_event = execution.state.get("history", [])[-1] if execution.state.get("history") else None
    persisted_world = await persist_designer_mutation(
        session,
        project=project,
        version=version,
        user=user,
        model=execution.model,
        action="COPILOT",
        event=last_event,
    )

    session.add(
        DecisionRecord(
            organization_id=project.organization_id,
            project_id=project.id,
            project_version_id=version.id,
            decision_type="COPILOT_EXECUTION",
            provider=proposal.provider,
            provider_model=proposal.model,
            provider_version=proposal.model_version,
            input_hash=canonical_hash(proposal.model_dump(mode="json")),
            question_schema_version=proposal.schema_version,
            inputs_json={
                "proposal_id": proposal.proposal_id,
                "context_hash": proposal.context_hash,
                "base_revision_hash": proposal.base_revision_hash,
                "evidence_ids": list(proposal.evidence_ids),
                "command_ids": [command.command_id for command in proposal.commands],
                "plan_fingerprint": plan.fingerprint,
                "approval_token_hash": canonical_hash({"approval_token": approval_token}),
            },
            outputs_json={
                "revision_hash": persisted_world.model_hash,
                "results": [result.model_dump(mode="json") for result in execution.results],
                "invalidated_artifact_ids": list(invalidated_artifact_ids),
                "impact_groups": list(plan.impact_groups),
            },
            decision="COMMITTED",
            confidence=proposal.confidence,
            request_id=proposal.proposal_id,
            human_override_json={"approval_required": proposal.requires_confirmation, "approved": True},
            final_disposition="CANONICAL_COMMIT",
        )
    )
    return version, execution.results, persisted_world.model_hash
