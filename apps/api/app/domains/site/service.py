from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.site_models import Site, SiteRevision
from app.db.models import Project, User
from app.domains.site.schemas import SetSiteBoundaryCommand
from app.domains.site.validation import validate_boundary
from app.domains.foundation.service import resolve_project_version


def _hash_boundary(boundary: dict[str, Any]) -> str:
    payload = json.dumps(boundary, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


async def set_site_boundary(session: AsyncSession, project: Project, user: User, body: SetSiteBoundaryCommand) -> SiteRevision:
    project_version = project.current_version_id
    if not project_version:
        raise ValueError("PROJECT_VERSION_REQUIRED")
    _, version = await resolve_project_version(session, project.id, project_version, user.id, write=True)
    existing = await session.scalar(select(Site).where(Site.project_id == project.id).order_by(Site.created_at.asc()))
    if existing is None:
        site = Site(organization_id=project.organization_id, project_id=project.id, created_by=user.id, name=body.name)
        session.add(site)
        await session.flush()
    else:
        site = existing
        if body.name.strip():
            site.name = body.name.strip()
    current = await session.scalar(select(SiteRevision).where(SiteRevision.site_id == site.id).order_by(SiteRevision.revision.desc()))
    if body.base_revision_hash:
        if current is None or current.content_hash != body.base_revision_hash:
            raise ValueError("STALE_SITE_REVISION")
    result = validate_boundary(body.boundary)
    revision_number = 1 if current is None else current.revision + 1
    revision = SiteRevision(
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        site_id=site.id,
        revision=revision_number,
        parent_revision_id=current.id if current else None,
        boundary_geojson=result.geojson,
        boundary_crs="EPSG:4326",
        calculation_crs=result.calculation_crs,
        area_m2=result.area_m2,
        perimeter_m=result.perimeter_m,
        content_hash=_hash_boundary(result.geojson),
        validation_json={"status": "VALID", "warnings": list(result.warnings)},
        created_by=user.id,
    )
    session.add(revision)
    await session.commit()
    await session.refresh(revision)
    return revision
