from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.architectural_model_models import ArchitecturalModelRevision
from app.db.models import Project, ProjectVersion
from app.domains.lifecycle.service import canonical_hash

from .schemas import ArchitecturalModel


class CanonicalModelConflict(HTTPException):
    def __init__(self, message: str = "The canonical model changed since it was read") -> None:
        super().__init__(409, {"error": {"code": "MODEL_REVISION_CONFLICT", "message": message}})


def _stored_model(row: ArchitecturalModelRevision) -> ArchitecturalModel:
    model = ArchitecturalModel.model_validate(row.model_json)
    if model.revision != row.revision or row.model_hash != canonical_hash(row.model_json):
        raise HTTPException(500, {"error": {"code": "MODEL_INTEGRITY_FAILURE", "message": "Stored architectural model failed integrity verification"}})
    return model


async def get_current_model(session: AsyncSession, project_id: str) -> tuple[ArchitecturalModelRevision, ArchitecturalModel] | None:
    row = await session.scalar(
        select(ArchitecturalModelRevision)
        .where(ArchitecturalModelRevision.project_id == project_id)
        .order_by(ArchitecturalModelRevision.revision.desc())
        .limit(1)
    )
    return None if row is None else (row, _stored_model(row))


async def get_model_revision(
    session: AsyncSession, project_id: str, revision: int
) -> tuple[ArchitecturalModelRevision, ArchitecturalModel]:
    row = await session.scalar(
        select(ArchitecturalModelRevision).where(
            ArchitecturalModelRevision.project_id == project_id,
            ArchitecturalModelRevision.revision == revision,
        )
    )
    if row is None:
        raise HTTPException(404, {"error": {"code": "MODEL_REVISION_NOT_FOUND", "message": "Architectural model revision not found"}})
    return row, _stored_model(row)


async def persist_model(
    session: AsyncSession,
    *,
    project: Project,
    version: ProjectVersion,
    model: ArchitecturalModel,
    actor_id: str,
    expected_revision: int | None,
    parent_revision_id: str | None = None,
    source: str = "user",
    change_summary: str = "",
) -> ArchitecturalModelRevision:
    current = await session.scalar(
        select(ArchitecturalModelRevision)
        .where(ArchitecturalModelRevision.project_id == project.id)
        .order_by(ArchitecturalModelRevision.revision.desc())
        .limit(1)
        .with_for_update()
    )
    current_revision = current.revision if current else 0
    if expected_revision is not None and expected_revision != current_revision:
        raise CanonicalModelConflict(
            f"Expected model revision {expected_revision}, current revision is {current_revision}"
        )
    expected_next = current_revision + 1
    if model.revision != expected_next:
        raise HTTPException(
            422,
            {"error": {"code": "INVALID_MODEL_REVISION", "message": f"Persisted model must be revision {expected_next}"}},
        )
    if parent_revision_id is None and current is not None:
        parent_revision_id = current.id
    payload = model.model_dump(mode="json", exclude_none=False)
    row = ArchitecturalModelRevision(
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        revision=model.revision,
        model_hash=canonical_hash(payload),
        model_json=payload,
        parent_revision_id=parent_revision_id,
        source=source,
        change_summary=change_summary,
        created_by=actor_id,
    )
    session.add(row)
    await session.flush()
    return row


def model_summary(row: ArchitecturalModelRevision, model: ArchitecturalModel) -> dict[str, Any]:
    return {
        "revision": row.revision,
        "model_hash": row.model_hash,
        "project_version_id": row.project_version_id,
        "parent_revision_id": row.parent_revision_id,
        "source": row.source,
        "change_summary": row.change_summary,
        "created_at": row.created_at.isoformat(),
        "model": model.model_dump(mode="json", exclude_none=False),
    }
