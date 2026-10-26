from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .release_gate import ReleaseBlocker, evaluate_release
from .release_manifest import ReleaseManifest, build_release_manifest, verify_release_manifest


@dataclass(frozen=True)
class ReleasePackage:
    ready: bool
    manifest: ReleaseManifest
    blockers: tuple[ReleaseBlocker, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"ready": self.ready, "manifest": self.manifest.as_dict(), "blockers": [{"code": b.code, "artifact_id": b.artifact_id, "artifact_type": b.artifact_type, "message": b.message, "dependency_path": list(b.dependency_path)} for b in self.blockers]}


async def build_release_package(session: AsyncSession, *, project_version_id: str) -> ReleasePackage:
    gate = await evaluate_release(session, project_version_id=project_version_id)
    manifest = await build_release_manifest(session, project_version_id=project_version_id)
    if not verify_release_manifest(manifest):
        raise RuntimeError("release manifest failed self-integrity verification")
    return ReleasePackage(ready=gate.ready, manifest=manifest, blockers=gate.blockers)
