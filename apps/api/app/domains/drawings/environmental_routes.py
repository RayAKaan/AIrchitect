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

from .environmental_spatial import analyze_environmental_spatial_performance


router = APIRouter(tags=["environmental-spatial-analysis"])


@router.post("/projects/{project_id}/environmental-spatial-analysis/generate", status_code=201)
async def generate_environmental_spatial_analysis(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project = await resolve_project(session, project_id, user.id)
    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None or version.status != "COMMITTED":
        raise HTTPException(409, {"error": {"code": "VERSION_NOT_READY", "message": "Commit the current project version before running spatial analysis"}})
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
        payload = analyze_environmental_spatial_performance(model)
    except ValueError as exc:
        raise HTTPException(422, {"error": {"code": "SPATIAL_ANALYSIS_INVALID", "message": str(exc)}}) from exc
    digest = payload["analysis_hash"]
    existing = await session.scalar(
        select(ArtifactVersion).where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "environmental_spatial_analysis",
            ArtifactVersion.output_hash == digest,
            ArtifactVersion.status == "current",
        ).order_by(ArtifactVersion.version.desc()).limit(1)
    )
    if existing is not None:
        return {"artifact_id": existing.id, "analysis_hash": digest,
                "analysis": existing.payload_json, "idempotent": True}
    previous = list((await session.scalars(
        select(ArtifactVersion).where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "environmental_spatial_analysis",
            ArtifactVersion.status == "current",
        )
    )).all())
    for item in previous:
        item.status = "stale"
    artifact = await new_artifact(
        session, project=project, version=version, world=world, actor=user.id,
        artifact_type="environmental_spatial_analysis", payload=payload,
        dependencies=[], status="current",
    )
    artifact.output_hash = digest
    await session.commit()
    return {"artifact_id": artifact.id, "analysis_hash": digest,
            "analysis": payload, "idempotent": False}


@router.get("/projects/{project_id}/environmental-spatial-analysis")
async def get_environmental_spatial_analysis(
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
            ArtifactVersion.artifact_type == "environmental_spatial_analysis",
        ).order_by(ArtifactVersion.version.desc()).limit(1)
    )
    if artifact is None:
        raise HTTPException(404, {"error": {"code": "SPATIAL_ANALYSIS_NOT_FOUND", "message": "No environmental and spatial analysis is available"}})
    current = await get_current_model(session, project_id)
    current_hash = model_hash(current[1]) if current else None
    stale = artifact.status != "current" or artifact.payload_json.get("source_model_hash") != current_hash
    return {"artifact_id": artifact.id, "analysis_hash": artifact.output_hash,
            "status": "STALE" if stale else "CURRENT", "analysis": artifact.payload_json}
