from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactVersion

from .artifact_invalidation import ArtifactInvalidationService
from .regeneration_executor import RegenerationHandlerRegistry
from .regeneration_queue import RegenerationQueue
from .regeneration_repository import RegenerationStateRepository


async def invalidate_and_enqueue(
    session: AsyncSession,
    *,
    project: Any,
    version: Any,
    source_revision_hash: str,
    groups: Sequence[str],
) -> tuple[str, ...]:
    """Invalidate affected artifacts and enqueue only supported regeneration work."""
    invalidated_artifact_ids = await ArtifactInvalidationService().invalidate_groups(
        session,
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        source_revision_hash=source_revision_hash,
        groups=groups,
    )
    if not invalidated_artifact_ids:
        return ()

    states = RegenerationStateRepository()
    queue = RegenerationQueue(states)
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
    return tuple(invalidated_artifact_ids)
