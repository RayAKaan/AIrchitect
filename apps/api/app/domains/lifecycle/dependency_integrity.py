from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactDependency, ArtifactVersion


@dataclass(frozen=True)
class DependencyIntegrityError:
    code: str
    artifact_id: str
    dependency_id: str | None = None


async def validate_dependency_integrity(session: AsyncSession, *, project_version_id: str) -> tuple[DependencyIntegrityError, ...]:
    artifacts = list((await session.scalars(select(ArtifactVersion).where(ArtifactVersion.project_version_id == project_version_id))).all())
    ids = {artifact.id for artifact in artifacts}
    errors: list[DependencyIntegrityError] = []
    rows = list((await session.scalars(select(ArtifactDependency).where(ArtifactDependency.artifact_version_id.in_(ids)))).all()) if ids else []
    adjacency: dict[str, set[str]] = {artifact_id: set() for artifact_id in ids}
    for row in rows:
        if row.depends_on_artifact_version_id not in ids:
            errors.append(DependencyIntegrityError("DEPENDENCY_OUTSIDE_VERSION", row.artifact_version_id, row.depends_on_artifact_version_id))
            continue
        if row.depends_on_artifact_version_id == row.artifact_version_id:
            errors.append(DependencyIntegrityError("SELF_DEPENDENCY", row.artifact_version_id, row.depends_on_artifact_version_id))
            continue
        adjacency[row.artifact_version_id].add(row.depends_on_artifact_version_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            errors.append(DependencyIntegrityError("DEPENDENCY_CYCLE", node))
            return
        if node in visited:
            return
        visiting.add(node)
        for dependency in sorted(adjacency[node]):
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for artifact_id in sorted(ids):
        visit(artifact_id)
    return tuple(errors)
