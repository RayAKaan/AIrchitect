from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactVersion, ProjectVersion, User, WorldModelRevision
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.foundation.service import resolve_project
from app.domains.lifecycle.service import new_artifact
from app.domains.model import model_hash
from app.domains.model.persistence import get_current_model

from .canonical import CanonicalRegulatoryRequest, build_canonical_regulatory_package


router = APIRouter(tags=["canonical-regulatory-evidence"])


@router.post("/projects/{project_id}/regulatory-evidence/generate", status_code=201)
async def generate_canonical_regulatory_evidence(
    project_id: str,
    body: CanonicalRegulatoryRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project = await resolve_project(session, project_id, user.id)
    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None or version.status != "COMMITTED":
        raise HTTPException(409, {"error": {"code": "VERSION_NOT_READY", "message": "Commit the current project version before regulatory screening"}})
    current = await get_current_model(session, project_id)
    if current is None or current[0].project_version_id != version.id:
        raise HTTPException(409, {"error": {"code": "MODEL_VERSION_MISMATCH", "message": "A canonical model for the current project version is required"}})
    _, model = current
    world = await session.scalar(
        select(WorldModelRevision).where(WorldModelRevision.project_version_id == version.id)
        .order_by(WorldModelRevision.revision.desc()).limit(1)
    )
    if world is None:
        raise HTTPException(409, {"error": {"code": "WORLD_MODEL_REQUIRED", "message": "A current World Model revision is required"}})
    try:
        payload = build_canonical_regulatory_package(model, version.id, body)
    except ValueError as exc:
        raise HTTPException(422, {"error": {"code": "REGULATORY_EVIDENCE_INVALID", "message": str(exc)}}) from exc
    digest = payload["package_hash"]
    existing = await session.scalar(
        select(ArtifactVersion).where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "canonical_regulatory_evidence",
            ArtifactVersion.output_hash == digest,
            ArtifactVersion.status == "current",
        ).order_by(ArtifactVersion.version.desc()).limit(1)
    )
    if existing is not None:
        return {"artifact_id": existing.id, "package_hash": digest,
                "package": existing.payload_json, "idempotent": True}
    previous = list((await session.scalars(
        select(ArtifactVersion).where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "canonical_regulatory_evidence",
            ArtifactVersion.status == "current",
        )
    )).all())
    for item in previous:
        item.status = "stale"
    artifact = await new_artifact(
        session, project=project, version=version, world=world, actor=user.id,
        artifact_type="canonical_regulatory_evidence", payload=payload,
        dependencies=[], status="current",
    )
    artifact.output_hash = digest
    await session.commit()
    return {"artifact_id": artifact.id, "package_hash": digest,
            "package": payload, "idempotent": False}


@router.get("/projects/{project_id}/regulatory-evidence")
async def get_canonical_regulatory_evidence(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project = await resolve_project(session, project_id, user.id)
    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None:
        raise HTTPException(404, "Current project version not found")
    artifact = await session.scalar(
        select(ArtifactVersion).where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "canonical_regulatory_evidence",
        ).order_by(ArtifactVersion.version.desc()).limit(1)
    )
    if artifact is None:
        raise HTTPException(404, {"error": {"code": "REGULATORY_EVIDENCE_NOT_FOUND", "message": "No canonical regulatory evidence package is available"}})
    current = await get_current_model(session, project_id)
    current_hash = model_hash(current[1]) if current else None
    stale = artifact.status != "current" or artifact.payload_json.get("source_model_hash") != current_hash
    return {"artifact_id": artifact.id, "package_hash": artifact.output_hash,
            "status": "STALE" if stale else "CURRENT", "package": artifact.payload_json}
