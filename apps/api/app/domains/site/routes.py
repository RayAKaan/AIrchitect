from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, User
from app.db.site_models import Site, SiteEvidence, SiteLayerSnapshot, SiteRevision
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from app.domains.site.analysis import RUNNER_VERSION, _hash, analyze_site
from app.domains.site.provider_runtime import fetch_context
from app.domains.site.schemas import ContextFetchOut, SetSiteBoundaryCommand, SiteAnalysisOut, SiteRevisionOut
from app.domains.site.service import set_site_boundary

router = APIRouter(tags=["site"])


def _revision_out(revision: SiteRevision) -> SiteRevisionOut:
    return SiteRevisionOut(site_id=revision.site_id, site_revision_id=revision.id, revision=revision.revision,
        boundary=revision.boundary_geojson, boundary_crs=revision.boundary_crs, calculation_crs=revision.calculation_crs,
        area_m2=revision.area_m2, perimeter_m=revision.perimeter_m, content_hash=revision.content_hash,
        parent_revision_id=revision.parent_revision_id)


async def _load_revision(session: AsyncSession, site_id: str, revision_ref: str) -> SiteRevision:
    query = select(SiteRevision).where(SiteRevision.site_id == site_id)
    revision = await session.scalar(query.where(SiteRevision.id == revision_ref))
    if revision is None and revision_ref.isdigit(): revision = await session.scalar(query.where(SiteRevision.revision == int(revision_ref)))
    if revision is None: raise HTTPException(404, "Site revision not found")
    return revision


@router.post("/projects/{project_id}/sites", response_model=SiteRevisionOut, status_code=201)
async def create_site_boundary(project_id: str, body: SetSiteBoundaryCommand, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> SiteRevisionOut:
    project = await session.get(Project, project_id)
    if project is None: raise HTTPException(404, "Project not found")
    await require_membership(project.organization_id, user, session, {"owner", "admin", "member"})
    try: revision = await set_site_boundary(session, project, user, body)
    except ValueError as exc:
        code = str(exc); status_code = 409 if code in {"STALE_SITE_REVISION", "PROJECT_VERSION_REQUIRED", "IDEMPOTENCY_KEY_REUSED", "SITE_COMMAND_INCOMPLETE"} else 422
        raise HTTPException(status_code, code) from exc
    return _revision_out(revision)


@router.get("/sites/{site_id}/revisions/{revision_ref}", response_model=SiteRevisionOut)
async def get_site_revision(site_id: str, revision_ref: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> SiteRevisionOut:
    site = await session.get(Site, site_id)
    if site is None: raise HTTPException(404, "Site not found")
    await require_membership(site.organization_id, user, session)
    return _revision_out(await _load_revision(session, site_id, revision_ref))


@router.post("/sites/{site_id}/revisions/{revision_ref}/context/{provider_id}", response_model=ContextFetchOut)
async def fetch_site_context(site_id: str, revision_ref: str, provider_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> ContextFetchOut:
    site = await session.get(Site, site_id)
    if site is None: raise HTTPException(404, "Site not found")
    await require_membership(site.organization_id, user, session, {"owner", "admin", "member"})
    revision = await _load_revision(session, site_id, revision_ref)
    try: result = await fetch_context(session, revision, provider_id)
    except ValueError as exc:
        code = str(exc); status_code = 422 if code.startswith("PROVIDER_") else 409
        raise HTTPException(status_code, code) from exc
    return ContextFetchOut(provider_id=result.provider_id, dataset_version=result.dataset_version, feature_count=result.feature_count,
        source_id=result.source_id, snapshot_id=result.snapshot_id, content_hash=result.content_hash, status=result.status)


@router.post("/sites/{site_id}/revisions/{revision_ref}/analysis", response_model=SiteAnalysisOut)
async def analyze_site_revision(site_id: str, revision_ref: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> SiteAnalysisOut:
    site = await session.get(Site, site_id)
    if site is None: raise HTTPException(404, "Site not found")
    await require_membership(site.organization_id, user, session, {"owner", "admin", "member"})
    revision = await _load_revision(session, site_id, revision_ref)
    snapshots = list(await session.scalars(select(SiteLayerSnapshot).where(SiteLayerSnapshot.site_revision_id == revision.id, SiteLayerSnapshot.layer_type == "CONTEXT")))
    result = analyze_site(revision, snapshots)
    existing = await session.scalar(select(SiteLayerSnapshot).where(SiteLayerSnapshot.site_revision_id == revision.id, SiteLayerSnapshot.layer_type == "ANALYSIS"))
    if existing is not None and existing.payload_json.get("source_context_hash") == result["source_context_hash"] and existing.payload_json.get("runner_version") == RUNNER_VERSION:
        return SiteAnalysisOut(analysis_snapshot_id=existing.id, site_revision_id=revision.id, source_context_hash=result["source_context_hash"], runner_version=RUNNER_VERSION, status=existing.status, result=existing.payload_json)
    snapshot = SiteLayerSnapshot(site_revision_id=revision.id, layer_type="ANALYSIS", provider="deterministic-site-analysis", dataset_version=RUNNER_VERSION, payload_json=result, status=result["status"])
    session.add(snapshot)
    session.add(SiteEvidence(site_revision_id=revision.id, claim_type="site_analysis", value_json={"runner_version": RUNNER_VERSION, "source_context_hash": result["source_context_hash"], "result_hash": _hash(result)}, confidence=1.0 if snapshots else None, status=result["status"], method=RUNNER_VERSION))
    await session.commit(); await session.refresh(snapshot)
    return SiteAnalysisOut(analysis_snapshot_id=snapshot.id, site_revision_id=revision.id, source_context_hash=result["source_context_hash"], runner_version=RUNNER_VERSION, status=snapshot.status, result=result)


@router.get("/sites/{site_id}/evidence")
async def get_site_evidence(site_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    site = await session.get(Site, site_id)
    if site is None: raise HTTPException(404, "Site not found")
    await require_membership(site.organization_id, user, session)
    rows = await session.scalars(select(SiteEvidence).join(SiteRevision, SiteEvidence.site_revision_id == SiteRevision.id).where(SiteRevision.site_id == site_id))
    return [{"id": item.id, "site_revision_id": item.site_revision_id, "source_id": item.source_id, "claim_type": item.claim_type,
             "value": item.value_json, "confidence": item.confidence, "status": item.status, "method": item.method} for item in rows]
