from app.domains.lifecycle.release_manifest import ReleaseArtifact, ReleaseManifest, verify_release_manifest


def test_release_manifest_integrity_verification():
    item = ReleaseArtifact("a", "geometry", 1, "h", {}, ())
    manifest = ReleaseManifest("v", (item,), "")
    from app.domains.lifecycle.release_manifest import _hash_payload
    valid = ReleaseManifest("v", (item,), _hash_payload("v", (item,)))
    assert verify_release_manifest(valid)
    assert not verify_release_manifest(manifest)
