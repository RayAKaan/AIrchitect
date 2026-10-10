from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactVersion, Project, User, WorldModelRevision
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from app.domains.foundation.service import error, resolve_project_version, resolve_world_model

from .engine import analyze
from .persistence import dependency_graph_snapshot, propagate_artifact_change
from .schemas import ChangeImpactRequest, ChangeImpactResponse, PersistedChangeRequest

router = APIRouter(tags=["change-impact"])


@router.post("/change-impact/analyze", response_model=ChangeImpactResponse, deprecated=True)
async def analyze_change(
    body: ChangeImpactRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ChangeImpactResponse:
    """Compatibility-only analysis for caller-supplied graphs; does not mutate state."""
    project = await session.get(Project, body.project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    await require_membership(project.organization_id, user, session)
    return analyze(body)


def flatten(value, prefix=""):
    out = {}
    if isinstance(value, dict):
        for key, nested in value.items():
            out.update(flatten(nested, f"{prefix}.{key}" if prefix else key))
    else:
        out[prefix] = value
    return out


@router.get("/projects/{project_id}/versions/{version_ref}/change-impact/graph")
async def persisted_dependency_graph(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return the authoritative persisted artifact graph for one authorized version."""
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    return await dependency_graph_snapshot(session, project, version, world)


@router.post("/projects/{project_id}/versions/{version_ref}/change-impact/propagate")
async def propagate_persisted_change(
    project_id: str,
    version_ref: str,
    body: PersistedChangeRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    """Atomically stale transitive dependants of changed persisted artifacts.

    The client supplies changed artifact IDs and a reason, never the graph itself.
    The expected World Model hash prevents propagation against a stale page state.
    """
    project, version = await resolve_project_version(
        session, project_id, version_ref, user.id, write=True
    )
    world = await resolve_world_model(session, version.id)
    if body.expected_world_model_hash != world.model_hash:
        raise error(
            409,
            "SOURCE_REVISION_CONFLICT",
            "The canonical World Model changed; refresh the graph before propagating impact.",
            expected_hash=body.expected_world_model_hash,
            current_hash=world.model_hash,
        )
    try:
        result = await propagate_artifact_change(
            session,
            project=project,
            version=version,
            actor_id=user.id,
            world=world,
            changed_artifact_ids=body.changed_artifact_ids,
            reason=body.reason,
        )
    except ValueError:
        # Keep unknown/cross-project artifact identifiers indistinguishable.
        raise error(404, "ARTIFACT_NOT_FOUND", "One or more changed artifacts were not found") from None
    await session.commit()
    return result


@router.get("/projects/{project_id}/versions/{version_ref}/change-impact")
async def persisted_impact(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    current = await session.scalar(
        select(WorldModelRevision)
        .where(WorldModelRevision.project_version_id == version.id)
        .order_by(WorldModelRevision.revision.desc())
        .limit(1)
    )
    if current is None:
        raise error(409, "WORLD_MODEL_NOT_READY", "The project version has no canonical World Model")
    previous = None
    if version.parent_version_id:
        previous = await session.scalar(
            select(WorldModelRevision)
            .where(WorldModelRevision.project_version_id == version.parent_version_id)
            .order_by(WorldModelRevision.revision.desc())
            .limit(1)
        )
    before = flatten(previous.model_json) if previous else {}
    after = flatten(current.model_json)
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))

    artifacts = list((await session.scalars(
        select(ArtifactVersion)
        .where(ArtifactVersion.project_version_id == version.id)
        .order_by(ArtifactVersion.created_at, ArtifactVersion.id)
    )).all())
    affected, unaffected = [], []
    for artifact in artifacts:
        item = {
            "artifact_version_id": artifact.id,
            "artifact_type": artifact.artifact_type,
            "version": artifact.version,
            "status": artifact.status,
            "source_world_model_revision_id": artifact.world_model_revision_id,
            "source_hash_current": artifact.world_model_revision_id == current.id,
            "reason": (
                "A source or transitive dependency is stale; recomputation/review is required."
                if str(artifact.status).upper() == "STALE"
                else "No persisted stale status is currently recorded for this artifact."
            ),
            "immutable": True,
        }
        (affected if str(artifact.status).upper() == "STALE" else unaffected).append(item)

    graph = await dependency_graph_snapshot(session, project, version, current)
    return {
        "project_id": project_id,
        "project_version_id": version.id,
        "parent_version_id": version.parent_version_id,
        "world_model_revision_id": current.id,
        "world_model_hash": current.model_hash,
        "changed_fields": changed,
        "affected": affected,
        "unaffected": unaffected,
        "dependency_graph": graph,
        "selective_recomputation": True,
        "recomputation_scheduled": False,
        "old_artifact_payloads_immutable": True,
    }
