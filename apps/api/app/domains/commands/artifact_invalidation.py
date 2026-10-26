from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactVersion
from app.db.regeneration_models import RegenerationStateRecord

from .regeneration_repository import RegenerationStateRepository

# Impact groups are domain-level names. This map is the single translation
# boundary into persisted artifact types; unknown groups fail closed rather
# than silently skipping invalidation.
GROUP_TO_ARTIFACT_TYPE: dict[str, str] = {
    "planning_envelope": "planning_envelope",
    "design_alternatives": "design_alternative",
    "parametric_geometry_intents": "geometry",
    "program": "program",
    "quantities": "quantities",
    "cost": "cost",
    "structural_review": "structural_review",
    "validation": "validation",
}


class ArtifactInvalidationService:
    """Atomically mark affected artifacts stale and persist regeneration state."""

    def __init__(self, repository: RegenerationStateRepository | None = None) -> None:
        self._repository = repository or RegenerationStateRepository()

    async def invalidate_groups(
        self,
        session: AsyncSession,
        *,
        organization_id: str,
        project_id: str,
        project_version_id: str,
        source_revision_hash: str,
        groups: Sequence[str],
    ) -> tuple[str, ...]:
        artifact_types = self._resolve_artifact_types(groups)
        if not artifact_types:
            return ()

        result = await session.execute(
            select(ArtifactVersion)
            .where(
                ArtifactVersion.organization_id == organization_id,
                ArtifactVersion.project_id == project_id,
                ArtifactVersion.project_version_id == project_version_id,
                ArtifactVersion.artifact_type.in_(artifact_types),
                ArtifactVersion.status == "current",
            )
            .with_for_update()
        )
        artifacts = list(result.scalars())
        invalidated: list[str] = []
        for artifact in artifacts:
            artifact.status = "stale"
            state = await self._repository.get_for_update(session, artifact.id)
            if state is None:
                await self._repository.create_invalidated(
                    session,
                    organization_id=organization_id,
                    project_id=project_id,
                    project_version_id=project_version_id,
                    artifact_version_id=artifact.id,
                    source_revision_hash=source_revision_hash,
                    generation_key=f"{artifact.artifact_type}:{source_revision_hash}",
                )
            else:
                await self._repository.invalidate(session, state, source_revision_hash)
            invalidated.append(artifact.id)
        await session.flush()
        return tuple(sorted(invalidated))

    @staticmethod
    def _resolve_artifact_types(groups: Sequence[str]) -> tuple[str, ...]:
        unknown = sorted(set(groups) - set(GROUP_TO_ARTIFACT_TYPE))
        if unknown:
            raise ValueError(f"unknown regeneration impact groups: {unknown}")
        return tuple(sorted({GROUP_TO_ARTIFACT_TYPE[group] for group in groups}))
