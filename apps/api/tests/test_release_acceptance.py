from app.domains.lifecycle.release_acceptance import evaluate_release_acceptance
from app.domains.lifecycle.release_manifest import ReleaseArtifact, ReleaseManifest
from app.domains.lifecycle.release_snapshot import ReleaseSnapshot


def _manifest() -> ReleaseManifest:
    artifact = ReleaseArtifact("a1", "geometry", 1, "hash-a", {}, ())
    from app.domains.lifecycle.release_manifest import _hash_payload

    return ReleaseManifest("v1", (artifact,), _hash_payload("v1", (artifact,)))


def test_release_acceptance_requires_snapshot_alignment() -> None:
    manifest = _manifest()
    snapshot = ReleaseSnapshot.create(
        project_version_id="v1",
        manifest_hash=manifest.manifest_hash,
        artifact_hashes={"a1": "hash-a"},
        dependency_revision_hash="deps",
    )
    result = evaluate_release_acceptance(
        manifest=manifest,
        snapshot=snapshot,
        required_artifact_types={"geometry"},
    )
    assert result.accepted
    assert result.reasons == ()


def test_release_acceptance_reports_missing_artifacts() -> None:
    manifest = _manifest()
    snapshot = ReleaseSnapshot.create(
        project_version_id="v1",
        manifest_hash=manifest.manifest_hash,
        artifact_hashes={"a1": "hash-a"},
        dependency_revision_hash="deps",
    )
    result = evaluate_release_acceptance(
        manifest=manifest,
        snapshot=snapshot,
        required_artifact_types={"geometry", "cost"},
    )
    assert not result.accepted
    assert "cost" in result.reasons[0]
