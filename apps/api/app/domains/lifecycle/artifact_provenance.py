from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.models import ArtifactVersion

SCHEMA_VERSION = "1.0.0"
REQUIRED_FIELDS = {
    "schema_version",
    "source_revision_hash",
    "dependency_hashes",
    "engine_version",
    "config_version",
}


def build_provenance(
    *,
    source_revision_hash: str,
    dependencies: list[ArtifactVersion],
    engine_version: str,
    config_version: str,
    generation_job_id: str | None = None,
) -> dict[str, Any]:
    if not source_revision_hash:
        raise ValueError("source_revision_hash must not be empty")
    if not engine_version.strip():
        raise ValueError("engine_version must not be empty")
    if not config_version.strip():
        raise ValueError("config_version must not be empty")
    dependency_hashes = [dependency.output_hash for dependency in dependencies]
    if any(not value for value in dependency_hashes):
        raise ValueError("all dependencies must have output hashes before provenance is recorded")
    provenance: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_revision_hash": source_revision_hash,
        "dependency_hashes": dependency_hashes,
        "engine_version": engine_version,
        "config_version": config_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if generation_job_id:
        provenance["generation_job_id"] = generation_job_id
    return provenance


def validate_provenance(artifact: ArtifactVersion, dependencies: list[ArtifactVersion]) -> tuple[str, ...]:
    provenance = artifact.provenance_json or {}
    errors = sorted(REQUIRED_FIELDS - provenance.keys())
    expected_hashes = [dependency.output_hash for dependency in dependencies]
    if provenance.get("dependency_hashes") != expected_hashes:
        errors.append("dependency_hashes_mismatch")
    if not isinstance(provenance.get("source_revision_hash"), str) or not provenance["source_revision_hash"]:
        errors.append("source_revision_hash_missing")
    if not isinstance(provenance.get("engine_version"), str) or not provenance["engine_version"]:
        errors.append("engine_version_missing")
    if not isinstance(provenance.get("config_version"), str) or not provenance["config_version"]:
        errors.append("config_version_missing")
    return tuple(dict.fromkeys(errors))
