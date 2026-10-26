from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactDependency, ArtifactVersion, Project, ProjectVersion, WorldModelRevision

from .service import canonical_hash


async def rebind_artifact(
    session: AsyncSession,
    *,
    project: Project,
    version: ProjectVersion,
    world: WorldModelRevision,
    previous_artifact_id: str,
    actor: str,
    payload: dict,
    source_revision_hash: str,
    dependencies: list[ArtifactVersion],
    engine_version: str,
) -> ArtifactVersion:
    """Publish a regenerated artifact as a new immutable version.

    The previous version is retained for audit/history and becomes stale. The new
    version receives fresh dependency edges in the same transaction. The caller is
    responsible for committing the surrounding regeneration transaction.
    """
    if not source_revision_hash:
        raise ValueError("source_revision_hash must not be empty")
    previous = await _locked_artifact(session, previous_artifact_id)
    if previous.project_id != project.id or previous.project_version_id != version.id:
        raise ValueError("artifact belongs to a different project or project version")
    if previous.status != "stale":
        raise ValueError(f"artifact must be stale before rebinding: {previous.status}")
    if any(dep.project_id != project.id or dep.project_version_id != version.id for dep in dependencies):
        raise ValueError("artifact dependencies must belong to the same project version")

    output_hash = canonical_hash(payload)
    candidates = list(
        (
            await session.scalars(
                select(ArtifactVersion)
                .where(
                    ArtifactVersion.project_version_id == version.id,
                    ArtifactVersion.artifact_type == previous.artifact_type,
                    ArtifactVersion.status == "current",
                    ArtifactVersion.output_hash == output_hash,
                )
                .order_by(ArtifactVersion.version.desc())
            )
        ).all()
    )
    current = next(
        (
            candidate
            for candidate in candidates
            if candidate.provenance_json.get("source_revision_hash") == source_revision_hash
        ),
        None,
    )
    if current is not None:
        previous.status = "stale"
        return current

    latest = await session.scalar(
        select(ArtifactVersion.version)
        .where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == previous.artifact_type,
        )
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
    )
    next_version = (latest or 0) + 1
    successor = ArtifactVersion(
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        world_model_revision_id=world.id,
        alternative_id=previous.alternative_id,
        artifact_type=previous.artifact_type,
        version=next_version,
        status="current",
        provenance_json={
            **previous.provenance_json,
            "created_from_canonical_state": True,
            "source_revision_hash": source_revision_hash,
            "engine_version": engine_version,
            "supersedes_artifact_version_id": previous.id,
        },
        input_references_json=[dependency.id for dependency in dependencies],
        output_hash=output_hash,
        payload_json=payload,
        created_by=actor,
    )
    session.add(successor)
    previous.status = "stale"
    await session.flush()
    for dependency in dependencies:
        session.add(
            ArtifactDependency(
                artifact_version_id=successor.id,
                depends_on_artifact_version_id=dependency.id,
                dependency_kind="input",
            )
        )
    await session.flush()
    return successor


async def _locked_artifact(session: AsyncSession, artifact_id: str) -> ArtifactVersion:
    result = await session.execute(
        select(ArtifactVersion).where(ArtifactVersion.id == artifact_id).with_for_update()
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise ValueError("artifact version not found")
    return artifact
