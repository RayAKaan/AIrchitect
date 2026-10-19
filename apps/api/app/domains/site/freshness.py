from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.site_models import Site, SiteEvidence, SiteLayerSnapshot, SiteRevision
from app.db.session import get_session
from app.dependencies import current_user, require_membership

router = APIRouter(tags=["site"])

@router.get("/sites/{site_id}/freshness")
async def site_freshness(site_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    site = await session.get(Site, site_id)
    if site is None: raise HTTPException(404, "Site not found")
    await require_membership(site.organization_id, user, session)
    revisions = list(await session.scalars(select(SiteRevision).where(SiteRevision.site_id == site_id).order_by(SiteRevision.revision.desc())))
    current = revisions[0] if revisions else None
    if current is None: return {"site_id": site_id, "current_revision_id": None, "artifacts": [], "evidence": []}
    revision_hashes = {revision.id: revision.content_hash for revision in revisions}
    snapshots = list(await session.scalars(select(SiteLayerSnapshot).join(SiteRevision, SiteLayerSnapshot.site_revision_id == SiteRevision.id).where(SiteRevision.site_id == site_id)))
    artifacts = [{"id": item.id, "layer_type": item.layer_type, "site_revision_id": item.site_revision_id, "status": "CURRENT" if item.site_revision_id == current.id else "STALE", "source_revision_hash": revision_hashes.get(item.site_revision_id)} for item in snapshots]
    evidence = list(await session.scalars(select(SiteEvidence).join(SiteRevision, SiteEvidence.site_revision_id == SiteRevision.id).where(SiteRevision.site_id == site_id)))
    evidence_state = [{"id": item.id, "site_revision_id": item.site_revision_id, "claim_type": item.claim_type, "status": "STALE" if item.site_revision_id != current.id else item.status} for item in evidence]
    return {"site_id": site_id, "current_revision_id": current.id, "current_revision": current.revision, "current_revision_hash": current.content_hash, "artifacts": artifacts, "evidence": evidence_state}
