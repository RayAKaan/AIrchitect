from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, User
from app.db.site_models import Site, SiteEvidence, SiteRevision
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from app.domains.site.schemas import SetSiteBoundaryCommand, SiteRevisionOut
from app.domains.site.service import set_site_boundary

router = APIRouter(tags=["site"])


@router.post("/projects/{project_id}/sites", response_model=SiteRevisionOut, status_code=201)
async def create_site_boundary(
    project_id: str,
    body: SetSiteBoundaryCommand,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> SiteRevisionOut:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    await require_membership(project.organization_id, user, session, {"owner", "admin", "member"})
    try:
        revision = await set_site_boundary(session, project, user, body)
    except ValueError as exc:
        code = str(exc)
        status_code = 409 if code in {"STALE_SITE_REVISION", "PROJECT_VERSION_REQUIRED"} else 422
        raise HTTPException(status_code, code) from exc
    return SiteRevisionOut(
        site_id=revision.site_id,
        site_revision_id=revision.id,
        revision=revision.revision,
        boundary=revision.boundary_geojson,
        boundary_crs=revision.boundary_crs,
        calculation_crs=revision.calculation_crs,
        area_m2=revision.area_m2,
        perimeter_m=revision.perimeter_m,
        content_hash=revision.content_hash,
        parent_revision_id=revision.parent_revision_id,
    )


@router.get("/sites/{site_id}/revisions/{revision_ref}", response_model=SiteRevisionOut)
async def get_site_revision(
    site_id: str,
    revision_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> SiteRevisionOut:
    site = await session.get(Site, site_id)
    if site is None:
        raise HTTPException(404, "Site not found")
    await require_membership(site.organization_id, user, session)
    query = select(SiteRevision).where(SiteRevision.site_id == site_id)
    revision = await session.scalar(query.where(SiteRevision.id == revision_ref))
    if revision is None and revision_ref.isdigit():
        revision = await session.scalar(query.where(SiteRevision.revision == int(revision_ref)))
    if revision is None:
        raise HTTPException(404, "Site revision not found")
    return SiteRevisionOut(
        site_id=revision.site_id, site_revision_id=revision.id, revision=revision.revision,
        boundary=revision.boundary_geojson, boundary_crs=revision.boundary_crs,
        calculation_crs=revision.calculation_crs, area_m2=revision.area_m2,
        perimeter_m=revision.perimeter_m, content_hash=revision.content_hash,
        parent_revision_id=revision.parent_revision_id,
    )


@router.get("/sites/{site_id}/evidence")
async def get_site_evidence(
    site_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    site = await session.get(Site, site_id)
    if site is None:
        raise HTTPException(404, "Site not found")
    await require_membership(site.organization_id, user, session)
    rows = await session.scalars(select(SiteEvidence).join(SiteRevision, SiteEvidence.site_revision_id == SiteRevision.id).where(SiteRevision.site_id == site_id))
    return [{"id": item.id, "site_revision_id": item.site_revision_id, "source_id": item.source_id,
             "claim_type": item.claim_type, "value": item.value_json, "confidence": item.confidence,
             "status": item.status, "method": item.method} for item in rows]
