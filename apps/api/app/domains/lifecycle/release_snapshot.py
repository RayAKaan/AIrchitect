from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReleaseSnapshot:
    """Pinned release inputs; later project mutations cannot change its identity."""

    project_version_id: str
    manifest_hash: str
    artifact_hashes: tuple[tuple[str, str], ...]
    dependency_revision_hash: str

    @classmethod
    def create(
        cls,
        *,
        project_version_id: str,
        manifest_hash: str,
        artifact_hashes: dict[str, str],
        dependency_revision_hash: str,
    ) -> ReleaseSnapshot:
        values = {
            "project_version_id": project_version_id,
            "manifest_hash": manifest_hash,
            "dependency_revision_hash": dependency_revision_hash,
        }
        for name, value in values.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        normalized = tuple(sorted((key, value) for key, value in artifact_hashes.items()))
        if any(not key.strip() or not value.strip() for key, value in normalized):
            raise ValueError("artifact hashes must contain non-empty ids and hashes")
        return cls(project_version_id, manifest_hash, normalized, dependency_revision_hash)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_version_id": self.project_version_id,
            "manifest_hash": self.manifest_hash,
            "artifact_hashes": dict(self.artifact_hashes),
            "dependency_revision_hash": self.dependency_revision_hash,
        }


def pin_snapshot(snapshot: ReleaseSnapshot) -> ReleaseSnapshot:
    return ReleaseSnapshot(
        snapshot.project_version_id,
        snapshot.manifest_hash,
        tuple(snapshot.artifact_hashes),
        snapshot.dependency_revision_hash,
    )
