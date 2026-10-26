from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactDependency, ArtifactVersion

from .artifact_provenance import validate_provenance
from .dependency_integrity import validate_dependency_integrity


DEFAULT_REQUIRED_TYPES = ("geometry", "quantity", "cost", "structural", "regulatory", "validation", "deliverable")


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


async def evaluate_release(session: AsyncSession, *, project_version_id: str, required_types: tuple[str, ...] = DEFAULT_REQUIRED_TYPES) -> ReleaseGateResult:
    artifacts = list((await session.scalars(select(ArtifactVersion).where(ArtifactVersion.project_version_id == project_version_id).order_by(ArtifactVersion.artifact_type, ArtifactVersion.version.desc(), ArtifactVersion.id))).all())
    integrity_errors = await validate_dependency_integrity(session, project_version_id=project_version_id)
    blockers = [ReleaseBlocker(code=error.code, artifact_id=error.artifact_id, artifact_type=None, message=f"Dependency integrity failure: {error.code}") for error in integrity_errors]
    current_by_type: dict[str, ArtifactVersion] = {}
    for artifact in artifacts:
        if artifact.artifact_type in required_types and artifact.artifact_type not in current_by_type and artifact.status == "current":
            current_by_type[artifact.artifact_type] = artifact
    for artifact_type in required_types:
        artifact = current_by_type.get(artifact_type)
        if artifact is None:
            blockers.append(ReleaseBlocker("MISSING_CURRENT_ARTIFACT", None, artifact_type, f"No current {artifact_type} artifact is available")); continue
        if artifact.output_hash is None:
            blockers.append(ReleaseBlocker("OUTPUT_HASH_MISSING", artifact.id, artifact.artifact_type, "Current artifact has no canonical output hash"))
        dependency_rows = list((await session.scalars(select(ArtifactDependency).where(ArtifactDependency.artifact_version_id == artifact.id))).all())
        dependency_ids = {row.depends_on_artifact_version_id for row in dependency_rows}
        dependencies = [dependency for dependency in artifacts if dependency.id in dependency_ids]
        blockers.extend(ReleaseBlocker(f"PROVENANCE_{code.upper()}", artifact.id, artifact.artifact_type, f"Provenance validation failed: {code}") for code in validate_provenance(artifact, dependencies))
        if artifact.status in {"stale", "failed", "unknown", "blocked"}:
            blockers.append(ReleaseBlocker("ARTIFACT_BLOCKED", artifact.id, artifact.artifact_type, f"Artifact status {artifact.status} is not releasable"))
    return ReleaseGateResult(ready=not blockers, blockers=tuple(blockers))
