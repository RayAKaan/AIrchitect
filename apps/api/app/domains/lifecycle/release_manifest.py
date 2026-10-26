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
        return {"project_version_id": self.project_version_id, "artifacts": [{"id": i.id, "artifact_type": i.artifact_type, "version": i.version, "output_hash": i.output_hash, "provenance": i.provenance, "dependency_ids": list(i.dependency_ids)} for i in self.artifacts], "manifest_hash": self.manifest_hash}


def _hash_payload(project_version_id: str, entries: tuple[ReleaseArtifact, ...]) -> str:
    canonical = json.dumps({"project_version_id": project_version_id, "artifacts": [{"id": i.id, "artifact_type": i.artifact_type, "version": i.version, "output_hash": i.output_hash, "provenance": i.provenance, "dependency_ids": list(i.dependency_ids)} for i in entries]}, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def verify_release_manifest(manifest: ReleaseManifest) -> bool:
    return manifest.manifest_hash == _hash_payload(manifest.project_version_id, manifest.artifacts)


async def build_release_manifest(session: AsyncSession, *, project_version_id: str) -> ReleaseManifest:
    artifacts = list((await session.scalars(select(ArtifactVersion).where(ArtifactVersion.project_version_id == project_version_id, ArtifactVersion.status == "current").order_by(ArtifactVersion.artifact_type, ArtifactVersion.version, ArtifactVersion.id))).all())
    dependencies = list((await session.scalars(select(ArtifactDependency).where(ArtifactDependency.artifact_version_id.in_([a.id for a in artifacts])).order_by(ArtifactDependency.artifact_version_id, ArtifactDependency.depends_on_artifact_version_id))).all()) if artifacts else []
    by_artifact = {artifact.id: [] for artifact in artifacts}
    for dependency in dependencies:
        by_artifact[dependency.artifact_version_id].append(dependency.depends_on_artifact_version_id)
    entries = tuple(ReleaseArtifact(a.id, a.artifact_type, a.version, a.output_hash or "", dict(a.provenance_json), tuple(by_artifact[a.id])) for a in artifacts)
    return ReleaseManifest(project_version_id, entries, _hash_payload(project_version_id, entries))
