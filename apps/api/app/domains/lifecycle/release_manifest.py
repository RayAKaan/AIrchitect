from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactDependency, ArtifactVersion


@dataclass(frozen=True)
class ReleaseArtifact:
    id: str
    artifact_type: str
    version: int
    output_hash: str
    provenance: dict[str, Any]
    dependency_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReleaseManifest:
    project_version_id: str
    artifacts: tuple[ReleaseArtifact, ...]
    manifest_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_version_id": self.project_version_id,
            "artifacts": [
                {
                    "id": item.id,
                    "artifact_type": item.artifact_type,
                    "version": item.version,
                    "output_hash": item.output_hash,
                    "provenance": item.provenance,
                    "dependency_ids": list(item.dependency_ids),
                }
                for item in self.artifacts
            ],
            "manifest_hash": self.manifest_hash,
        }


async def build_release_manifest(session: AsyncSession, *, project_version_id: str) -> ReleaseManifest:
    artifacts = list(
        (
            await session.scalars(
                select(ArtifactVersion)
                .where(
                    ArtifactVersion.project_version_id == project_version_id,
                    ArtifactVersion.status == "current",
                )
                .order_by(ArtifactVersion.artifact_type, ArtifactVersion.version, ArtifactVersion.id)
            )
        ).all()
    )
    dependencies = list(
        (
            await session.scalars(
                select(ArtifactDependency)
                .where(ArtifactDependency.artifact_version_id.in_([a.id for a in artifacts]))
                .order_by(ArtifactDependency.artifact_version_id, ArtifactDependency.depends_on_artifact_version_id)
            )
        ).all()
    )
    by_artifact: dict[str, list[str]] = {artifact.id: [] for artifact in artifacts}
    for dependency in dependencies:
        by_artifact[dependency.artifact_version_id].append(dependency.depends_on_artifact_version_id)

    entries = tuple(
        ReleaseArtifact(
            id=artifact.id,
            artifact_type=artifact.artifact_type,
            version=artifact.version,
            output_hash=artifact.output_hash or "",
            provenance=dict(artifact.provenance_json),
            dependency_ids=tuple(by_artifact[artifact.id]),
        )
        for artifact in artifacts
    )
    canonical = json.dumps(
        {
            "project_version_id": project_version_id,
            "artifacts": [
                {
                    "id": item.id,
                    "artifact_type": item.artifact_type,
                    "version": item.version,
                    "output_hash": item.output_hash,
                    "provenance": item.provenance,
                    "dependency_ids": list(item.dependency_ids),
                }
                for item in entries
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return ReleaseManifest(
        project_version_id=project_version_id,
        artifacts=entries,
        manifest_hash=hashlib.sha256(canonical).hexdigest(),
    )
