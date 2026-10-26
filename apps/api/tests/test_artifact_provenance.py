from __future__ import annotations

from app.db.models import ArtifactVersion
from app.domains.lifecycle.artifact_provenance import build_provenance, validate_provenance


def _artifact(provenance: dict) -> ArtifactVersion:
    return ArtifactVersion(
        organization_id="org",
        project_id="project",
        project_version_id="version",
        artifact_type="geometry",
        version=1,
        provenance_json=provenance,
        output_hash="a" * 64,
        payload_json={},
        created_by="user",
    )


def test_build_and_validate_provenance():
    dependency = _artifact({})
    dependency.output_hash = "b" * 64
    provenance = build_provenance(
        source_revision_hash="c" * 64,
        dependencies=[dependency],
        engine_version="geometry-v1",
        config_version="config-v1",
        generation_job_id="job-1",
    )
    artifact = _artifact(provenance)
    assert validate_provenance(artifact, [dependency]) == ()


def test_validate_provenance_detects_dependency_drift():
    dependency = _artifact({})
    dependency.output_hash = "b" * 64
    provenance = build_provenance(
        source_revision_hash="c" * 64,
        dependencies=[dependency],
        engine_version="geometry-v1",
        config_version="config-v1",
    )
    artifact = _artifact(provenance)
    dependency.output_hash = "d" * 64
    assert "dependency_hashes_mismatch" in validate_provenance(artifact, [dependency])
