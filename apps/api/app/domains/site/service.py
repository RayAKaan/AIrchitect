from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, ProjectVersion, User
from app.db.site_command_models import SiteCommandLog
from app.db.site_models import Site, SiteEvidence, SiteLayerSnapshot, SiteRevision
from app.domains.foundation.service import resolve_project_version
from app.domains.commands.artifact_lifecycle import invalidate_and_enqueue
from app.domains.site.schemas import SetSiteBoundaryCommand
from app.domains.site.validation import validate_boundary


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _command_payload_hash(boundary: dict[str, Any], name: str, reason: str) -> str:
    return _hash_payload({"boundary": boundary, "name": name, "reason": reason})


async def _materialize_stale_derived_state(
    session: AsyncSession,
    site_id: str,
    current_revision_id: str,
) -> None:
    """Persist stale state for every derived artifact from an older site revision.

    Freshness is still revision-authoritative, but materializing the state prevents
    consumers that read a snapshot directly from mistaking historical output for
    current output. Historical rows are preserved; only their lifecycle status is
    updated to STALE.
    """
    old_snapshots = list(
        await session.scalars(
            select(SiteLayerSnapshot)
            .where(
                SiteLayerSnapshot.site_revision_id != current_revision_id,
                SiteLayerSnapshot.site_revision_id.in_(
                    select(SiteRevision.id).where(SiteRevision.site_id == site_id)
                ),
            )
        )
    )
    for snapshot in old_snapshots:
        snapshot.status = "STALE"

    old_evidence = list(
        await session.scalars(
            select(SiteEvidence)
            .where(
                SiteEvidence.site_revision_id != current_revision_id,
                SiteEvidence.site_revision_id.in_(
                    select(SiteRevision.id).where(SiteRevision.site_id == site_id)
                ),
            )
        )
    )
    for evidence in old_evidence:
        evidence.status = "STALE"




SITE_ARTIFACT_IMPACT_GROUPS = (
    "planning_envelope",
    "design_alternatives",
    "parametric_geometry_intents",
    "quantities",
    "cost",
    "structural_review",
    "validation",
)


async def invalidate_site_artifacts(
    session: AsyncSession,
    project: Project,
    version: ProjectVersion,
    revision: SiteRevision,
) -> tuple[str, ...]:
    """Invalidate project artifacts bound to the superseded site boundary."""
    source_hash = _hash_payload({
        "site_revision_id": revision.id,
        "site_revision_hash": revision.content_hash,
    })
    return await invalidate_and_enqueue(
        session,
        project=project,
        version=version,
        source_revision_hash=source_hash,
        groups=list(SITE_ARTIFACT_IMPACT_GROUPS),
    )


async def set_site_boundary(session: AsyncSession, project: Project, user: User, body: SetSiteBoundaryCommand) -> SiteRevision:
    project_version = project.current_version_id
    if not project_version:
        raise ValueError("PROJECT_VERSION_REQUIRED")
    _, version = await resolve_project_version(session, project.id, project_version, user.id, write=True)

    result = validate_boundary(body.boundary)
    payload_hash = _command_payload_hash(result.geojson, body.name.strip(), body.reason.strip())
    existing_command = await session.scalar(
        select(SiteCommandLog).where(
            SiteCommandLog.project_id == project.id,
            SiteCommandLog.idempotency_key == body.idempotency_key,
        )
    )
    if existing_command is not None:
        if existing_command.payload_hash != payload_hash:
            raise ValueError("IDEMPOTENCY_KEY_REUSED")
        if existing_command.status == "COMMITTED" and existing_command.site_revision_id:
            revision = await session.get(SiteRevision, existing_command.site_revision_id)
            if revision is not None:
                return revision
        raise ValueError("SITE_COMMAND_INCOMPLETE")

    command_log = SiteCommandLog(
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        command_id=body.command_id,
        idempotency_key=body.idempotency_key,
        command_type="SetSiteBoundary",
        payload_hash=payload_hash,
        status="COMMITTING",
        created_by=user.id,
    )
    session.add(command_log)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing_command = await session.scalar(
            select(SiteCommandLog).where(
                SiteCommandLog.project_id == project.id,
                SiteCommandLog.idempotency_key == body.idempotency_key,
            )
        )
        if existing_command is None:
            raise
        if existing_command.payload_hash != payload_hash:
            raise ValueError("IDEMPOTENCY_KEY_REUSED")
        if existing_command.status == "COMMITTED" and existing_command.site_revision_id:
            revision = await session.get(SiteRevision, existing_command.site_revision_id)
            if revision is not None:
                return revision
        raise ValueError("SITE_COMMAND_INCOMPLETE")

    existing = await session.scalar(select(Site).where(Site.project_id == project.id).order_by(Site.created_at.asc()))
    if existing is None:
        site = Site(organization_id=project.organization_id, project_id=project.id, created_by=user.id, name=body.name.strip())
        session.add(site)
        await session.flush()
    else:
        site = existing
        if body.name.strip():
            site.name = body.name.strip()

    current = await session.scalar(select(SiteRevision).where(SiteRevision.site_id == site.id).order_by(SiteRevision.revision.desc()))
    if body.base_revision_hash and (current is None or current.content_hash != body.base_revision_hash):
        await session.rollback()
        raise ValueError("STALE_SITE_REVISION")

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
        content_hash=_hash_payload(result.geojson),
        validation_json={"status": "VALID", "warnings": list(result.warnings)},
        created_by=user.id,
    )
    session.add(revision)
    await session.flush()
    await _materialize_stale_derived_state(session, site.id, revision.id)
    await invalidate_site_artifacts(session, project, version, revision)
    command_log.status = "COMMITTED"
    command_log.site_revision_id = revision.id
    await session.commit()
    await session.refresh(revision)
    return revision
