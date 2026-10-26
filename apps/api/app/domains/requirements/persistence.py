from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RequirementRecord, User
from app.domains.foundation.service import audit, error, persist_world_model, resolve_project_version
from app.domains.requirements.service import analyze_brief


def _out(row: RequirementRecord) -> dict:
    return {
        "id": row.id,
        "parameter": row.parameter,
        "category": row.category,
        "value": row.normalized_value_json,
        "unit": row.unit,
        "source_text": row.source_text,
        "source_type": row.source_type,
        "extraction_method": row.extraction_method,
        "confidence": row.confidence,
        "status": row.status,
        "contradiction_group": row.contradiction_group,
        "provenance": row.provenance_json,
        "confirmed_at": row.confirmed_at,
    }


async def extract(session: AsyncSession, project_id: str, version_ref: str, user: User) -> dict:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    brief_model = __import__("app.db.models", fromlist=["BuildingBriefRecord"])
    brief = await session.scalar(
        select(brief_model.BuildingBriefRecord)
        .where(brief_model.BuildingBriefRecord.project_version_id == version.id)
        .order_by(brief_model.BuildingBriefRecord.revision.desc())
        .limit(1)
    )
    if brief is None:
        raise error(409, "BRIEF_REQUIRED", "Create a brief before extracting requirements")
    requirements, missing, issues = analyze_brief(brief.raw_text)
    existing = list(
        (
            await session.scalars(
                select(RequirementRecord).where(
                    RequirementRecord.project_version_id == version.id,
                    RequirementRecord.source_reference == brief.content_hash,
                )
            )
        ).all()
    )
    if existing:
        return {
            "brief_hash": brief.content_hash,
            "requirements": [_out(row) for row in existing],
            "missing_information": missing,
            "issues": issues,
            "idempotent": True,
        }
    groups: dict[str, str] = {}
    rows = []
    for candidate in requirements:
        group = groups.setdefault(candidate.parameter, str(uuid4()))
        row = RequirementRecord(
            organization_id=project.organization_id,
            project_id=project.id,
            project_version_id=version.id,
            source_text=candidate.source_text,
            parameter=candidate.parameter,
            category=candidate.category.value,
            raw_value_json=candidate.value,
            extracted_value_json=candidate.value,
            normalized_value_json=candidate.value,
            value_type=type(candidate.value).__name__,
            unit=candidate.unit,
            source_type="USER_BRIEF",
            source_reference=brief.content_hash,
            extraction_method="deterministic_pattern_v2",
            confidence=0.95,
            provenance_json={
                "brief_revision": brief.revision,
                "brief_hash": brief.content_hash,
                "source_text": candidate.source_text,
            },
            status="EXTRACTED",
            contradiction_group=(
                group
                if any(i.related_parameters and candidate.parameter in i.related_parameters for i in issues)
                else None
            ),
            created_by=user.id,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    await audit(
        session,
        project=project,
        version=version,
        actor=user.id,
        action="REQUIREMENTS_EXTRACTED",
        entity="requirement_set",
        entity_id=brief.content_hash,
        metadata={"count": len(rows), "brief_hash": brief.content_hash},
    )
    await session.commit()
    return {
        "brief_hash": brief.content_hash,
        "requirements": [_out(row) for row in rows],
        "missing_information": missing,
        "issues": issues,
        "idempotent": False,
    }


async def list_requirements(session: AsyncSession, project_id: str, version_ref: str, user: User) -> dict:
    _, version = await resolve_project_version(session, project_id, version_ref, user.id)
    rows = list(
        (
            await session.scalars(
                select(RequirementRecord)
                .where(RequirementRecord.project_version_id == version.id)
                .order_by(RequirementRecord.created_at, RequirementRecord.id)
            )
        ).all()
    )
    return {"project_version_id": version.id, "requirements": [_out(row) for row in rows]}


async def set_status(
    session: AsyncSession,
    project_id: str,
    version_ref: str,
    requirement_id: str,
    status: str,
    user: User,
    *,
    expected_revision: int | None = None,
) -> dict:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    if expected_revision is not None and version.revision_number != expected_revision:
        raise error(
            409,
            "VERSION_CONFLICT",
            "The project version changed since it was read",
            expected_revision=expected_revision,
            current_revision=version.revision_number,
        )
    row = await session.scalar(
        select(RequirementRecord)
        .where(
            RequirementRecord.id == requirement_id,
            RequirementRecord.project_version_id == version.id,
        )
        .with_for_update()
    )
    if row is None:
        raise error(404, "REQUIREMENT_NOT_FOUND", "Requirement not found")
    if row.status in {"REJECTED", "SUPERSEDED"}:
        raise error(409, "REQUIREMENT_CLOSED", "This requirement is already closed")
    if status == "CONFIRMED":
        row.status = "CONFIRMED"
        row.confirmed_by = user.id
        row.confirmed_at = datetime.now(timezone.utc)
    elif status == "REJECTED":
        row.status = "REJECTED"
    else:
        raise error(422, "INVALID_REQUIREMENT_STATUS", "Only CONFIRMED or REJECTED transitions are supported")
    version.revision_number += 1
    await audit(
        session,
        project=project,
        version=version,
        actor=user.id,
        action=f"REQUIREMENT_{status}",
        entity="requirement",
        entity_id=row.id,
        metadata={"parameter": row.parameter},
    )
    world = await persist_world_model(session, project, version, user.id, source="confirmed_requirements")
    await session.commit()
    return {
        "requirement": _out(row),
        "version_revision": version.revision_number,
        "world_model_revision_id": world.id,
        "world_model_hash": world.model_hash,
    }
