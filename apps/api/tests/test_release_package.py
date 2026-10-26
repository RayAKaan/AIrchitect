from app.domains.lifecycle.release_package import ReleasePackage
from app.domains.lifecycle.release_manifest import ReleaseArtifact, ReleaseManifest


def test_release_package_serialization_is_explicit():
    manifest = ReleaseManifest("v", (ReleaseArtifact("a", "geometry", 1, "h", {}, ()),), "hash")
    package = ReleasePackage(False, manifest, ())
    payload = package.as_dict()
    assert payload["ready"] is False
    assert payload["manifest"]["manifest_hash"] == "hash"
    assert payload["blockers"] == []
