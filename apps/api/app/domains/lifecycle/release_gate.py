from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactDependency, ArtifactVersion

from .artifact_provenance import validate_provenance


DEFAULT_REQUIRED_TYPES = (
    "geometry",
    "quantity",
    "cost",
    "structural",
    "regulatory",
    "validation",
    "deliverable",
)


@dataclass(frozen=True)
class ReleaseBlocker:
    code: str
    artifact_id: str | None
    artifact_type: str | None
    message: str
    dependency_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReleaseGateResult:
    ready: bool
    blockers: tuple[ReleaseBlocker, ...]


async def evaluate_release(
    session: AsyncSession,
    *,
    project_version_id: str,
    required_types: tuple[str, ...] = DEFAULT_REQUIRED_TYPES,
) -> ReleaseGateResult:
    artifacts = list(
        (
            await session.scalars(
                select(ArtifactVersion)
                .where(ArtifactVersion.project_version_id == project_version_id)
                .order_by(ArtifactVersion.artifact_type, ArtifactVersion.version.desc(), ArtifactVersion.id)
            )
        ).all()
    )
    current_by_type: dict[str, ArtifactVersion] = {}
    for artifact in artifacts:
        if artifact.artifact_type not in required_types:
            continue
        if artifact.artifact_type not in current_by_type and artifact.status == "current":
            current_by_type[artifact.artifact_type] = artifact

    blockers: list[ReleaseBlocker] = []
    for artifact_type in required_types:
        artifact = current_by_type.get(artifact_type)
        if artifact is None:
            blockers.append(
                ReleaseBlocker(
                    code="MISSING_CURRENT_ARTIFACT",
                    artifact_id=None,
                    artifact_type=artifact_type,
                    message=f"No current {artifact_type} artifact is available",
                )
            )
            continue
        if artifact.status != "current":
            blockers.append(
                ReleaseBlocker(
                    code="ARTIFACT_NOT_CURRENT",
                    artifact_id=artifact.id,
                    artifact_type=artifact.artifact_type,
                    message=f"Artifact is {artifact.status}, not current",
                )
            )
        if artifact.output_hash is None:
            blockers.append(
                ReleaseBlocker(
                    code="OUTPUT_HASH_MISSING",
                    artifact_id=artifact.id,
                    artifact_type=artifact.artifact_type,
                    message="Current artifact has no canonical output hash",
                )
            )
        dependency_rows = list(
            (
                await session.scalars(
                    select(ArtifactDependency).where(ArtifactDependency.artifact_version_id == artifact.id)
                )
            ).all()
        )
        dependency_ids = {row.depends_on_artifact_version_id for row in dependency_rows}
        dependencies = [dependency for dependency in artifacts if dependency.id in dependency_ids]
        provenance_errors = validate_provenance(artifact, dependencies)
        blockers.extend(
            ReleaseBlocker(
                code=f"PROVENANCE_{code.upper()}",
                artifact_id=artifact.id,
                artifact_type=artifact.artifact_type,
                message=f"Provenance validation failed: {code}",
            )
            for code in provenance_errors
        )
        if artifact.status in {"stale", "failed", "unknown", "blocked"}:
            blockers.append(
                ReleaseBlocker(
                    code="ARTIFACT_BLOCKED",
                    artifact_id=artifact.id,
                    artifact_type=artifact.artifact_type,
                    message=f"Artifact status {artifact.status} is not releasable",
                )
            )

    return ReleaseGateResult(ready=not blockers, blockers=tuple(blockers))
