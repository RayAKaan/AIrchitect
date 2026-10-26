from __future__ import annotations

from dataclasses import dataclass

from .release_manifest import ReleaseManifest, verify_release_manifest
from .release_snapshot import ReleaseSnapshot


@dataclass(frozen=True)
class ReleaseAcceptance:
    accepted: bool
    reasons: tuple[str, ...]


def evaluate_release_acceptance(
    *,
    manifest: ReleaseManifest,
    snapshot: ReleaseSnapshot,
    required_artifact_types: set[str],
) -> ReleaseAcceptance:
    reasons: list[str] = []
    if not verify_release_manifest(manifest):
        reasons.append("release manifest integrity verification failed")
    if manifest.project_version_id != snapshot.project_version_id:
        reasons.append("manifest and snapshot project versions differ")
    if manifest.manifest_hash != snapshot.manifest_hash:
        reasons.append("manifest and snapshot hashes differ")
    actual_types = {artifact.artifact_type for artifact in manifest.artifacts}
    missing = sorted(required_artifact_types - actual_types)
    if missing:
        reasons.append(f"missing required artifact types: {', '.join(missing)}")
    snapshot_hashes = dict(snapshot.artifact_hashes)
    for artifact in manifest.artifacts:
        expected_hash = snapshot_hashes.get(artifact.id)
        if expected_hash is not None and expected_hash != artifact.output_hash:
            reasons.append(f"artifact hash mismatch: {artifact.id}")
    return ReleaseAcceptance(not reasons, tuple(reasons))
