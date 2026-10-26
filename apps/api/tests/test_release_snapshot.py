import pytest

from app.domains.lifecycle.release_snapshot import ReleaseSnapshot, pin_snapshot


def test_snapshot_normalizes_artifact_order() -> None:
    snapshot = ReleaseSnapshot.create(
        project_version_id="v1",
        manifest_hash="manifest",
        artifact_hashes={"z": "z-hash", "a": "a-hash"},
        dependency_revision_hash="deps",
    )
    assert snapshot.artifact_hashes == (("a", "a-hash"), ("z", "z-hash"))
    assert pin_snapshot(snapshot) == snapshot


def test_snapshot_rejects_empty_identity() -> None:
    with pytest.raises(ValueError, match="project_version_id"):
        ReleaseSnapshot.create(
            project_version_id=" ",
            manifest_hash="manifest",
            artifact_hashes={},
            dependency_revision_hash="deps",
        )


def test_snapshot_is_independent_of_input_mapping_mutation() -> None:
    artifacts = {"a": "hash-a"}
    snapshot = ReleaseSnapshot.create(
        project_version_id="v1",
        manifest_hash="manifest",
        artifact_hashes=artifacts,
        dependency_revision_hash="deps",
    )
    artifacts["b"] = "hash-b"
    assert snapshot.as_dict()["artifact_hashes"] == {"a": "hash-a"}
