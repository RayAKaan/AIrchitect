from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from app.domains.foundation.service import resolve_project_version

from .release_gate import evaluate_release
from .release_manifest import build_release_manifest
from .release_package import build_release_package
from .runtime_health import check_runtime_health
from .runtime_observability import collect_runtime_metrics

router = APIRouter(tags=["runtime"])


@router.get("/health")
async def runtime_health(session: AsyncSession = Depends(get_session)):
    health = await check_runtime_health(session)
    return JSONResponse(content=health.as_dict(), status_code=200 if health.ready else 503)


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


@router.get("/projects/{project_id}/versions/{version_ref}/release-manifest")
async def release_manifest(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    manifest = await build_release_manifest(session, project_version_id=version.id)
    return JSONResponse(
        content={"project_id": project.id, **manifest.as_dict()},
        headers={"X-Release-Manifest-Hash": manifest.manifest_hash},
    )


@router.get("/projects/{project_id}/versions/{version_ref}/release-package")
async def release_package(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    package = await build_release_package(session, project_version_id=version.id)
    return JSONResponse(
        content={"project_id": project.id, "project_version_id": version.id, **package.as_dict()},
        headers={"X-Release-Manifest-Hash": package.manifest.manifest_hash},
    )


@router.get("/organizations/{organization_id}/runtime/metrics")
async def runtime_metrics(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_membership(organization_id, user, session)
    metrics = await collect_runtime_metrics(session, organization_id=organization_id)
    return metrics.as_dict()
