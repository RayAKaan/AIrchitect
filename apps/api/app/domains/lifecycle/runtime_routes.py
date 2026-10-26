from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from app.domains.foundation.service import resolve_project_version

from .release_gate import evaluate_release
from .runtime_observability import collect_runtime_metrics

router = APIRouter(tags=["runtime"])


@router.get("/projects/{project_id}/versions/{version_ref}/release-readiness")
async def release_readiness(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    result = await evaluate_release(session, project_version_id=version.id)
    return {
        "project_id": project.id,
        "project_version_id": version.id,
        "ready": result.ready,
        "blockers": [
            {
                "code": blocker.code,
                "artifact_id": blocker.artifact_id,
                "artifact_type": blocker.artifact_type,
                "message": blocker.message,
                "dependency_path": list(blocker.dependency_path),
            }
            for blocker in result.blockers
        ],
    }


@router.get("/organizations/{organization_id}/runtime/metrics")
async def runtime_metrics(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_membership(organization_id, user, session)
    metrics = await collect_runtime_metrics(session, organization_id=organization_id)
    return metrics.as_dict()
