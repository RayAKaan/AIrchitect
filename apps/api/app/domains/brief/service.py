from __future__ import annotations

import hashlib
import re
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import BuildingBriefRecord, Project, ProjectVersion, User
from app.domains.foundation.service import audit, error, resolve_project_version


def canonical_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\r\n", "\n").strip())


def content_hash(text: str, structured: dict) -> str:
    import json
    payload = json.dumps({"text": canonical_text(text), "structured": structured}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _out(row: BuildingBriefRecord) -> dict:
    return {"id": row.id, "project_id": row.project_id, "project_version_id": row.project_version_id,
        "revision": row.revision, "raw_text": row.raw_text, "structured": row.structured_json,
        "source_type": row.source_type, "source_reference": row.source_reference,
        "content_hash": row.content_hash, "created_at": row.created_at.isoformat()}

async def latest(session: AsyncSession, project_id: str, version_ref: str, user: User) -> dict | None:
    _, version = await resolve_project_version(session, project_id, version_ref, user.id)
    row = await session.scalar(select(BuildingBriefRecord).where(BuildingBriefRecord.project_version_id == version.id)
        .order_by(BuildingBriefRecord.revision.desc()).limit(1))
    return _out(row) if row else None

async def write(session: AsyncSession, project_id: str, version_ref: str, body, user: User) -> dict:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    text = canonical_text(body.raw_text)
    structured = body.structured or {}
    digest = content_hash(text, structured)
    current = await session.scalar(select(BuildingBriefRecord).where(BuildingBriefRecord.project_version_id == version.id)
        .order_by(BuildingBriefRecord.revision.desc()).limit(1))
    if current and current.content_hash == digest:
        return _out(current) | {"idempotent": True}
    revision = (current.revision + 1) if current else 1
    row = BuildingBriefRecord(organization_id=project.organization_id, project_id=project.id,
        project_version_id=version.id, revision=revision, raw_text=text, structured_json=structured,
        source_type=body.source_type, source_reference=body.source_reference, content_hash=digest,
        created_by=user.id)
    session.add(row); await session.flush()
    await audit(session, project=project, version=version, actor=user.id, action="BRIEF_REVISED",
        entity="building_brief", entity_id=row.id, metadata={"revision": revision, "content_hash": digest})
    await session.commit(); await session.refresh(row)
    return _out(row) | {"idempotent": False}

async def history(session: AsyncSession, project_id: str, version_ref: str, user: User) -> dict:
    _, version = await resolve_project_version(session, project_id, version_ref, user.id)
    rows = list((await session.scalars(select(BuildingBriefRecord).where(BuildingBriefRecord.project_version_id == version.id)
        .order_by(BuildingBriefRecord.revision.desc()))).all())
    return {"project_version_id": version.id, "revisions": [_out(row) for row in rows]}
