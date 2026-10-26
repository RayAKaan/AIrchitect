from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.regeneration_models import RegenerationStateRecord

from .regeneration_state import RegenerationState, invalidate


class RegenerationStateRepository:
    """Transactional persistence adapter for regeneration lifecycle state."""

    async def get_for_update(
        self, session: AsyncSession, artifact_version_id: str
    ) -> RegenerationStateRecord | None:
        result = await session.execute(
            select(RegenerationStateRecord)
            .where(RegenerationStateRecord.artifact_version_id == artifact_version_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create_current(
        self,
        session: AsyncSession,
        *,
        organization_id: str,
        project_id: str,
        project_version_id: str,
        artifact_version_id: str,
        source_revision_hash: str,
        generation_key: str,
    ) -> RegenerationStateRecord:
        record = RegenerationStateRecord(
            organization_id=organization_id,
            project_id=project_id,
            project_version_id=project_version_id,
            artifact_version_id=artifact_version_id,
            source_revision_hash=source_revision_hash,
            status="CURRENT",
            output_revision_hash=source_revision_hash,
            generation_key=generation_key,
        )
        session.add(record)
        await session.flush()
        return record

    async def invalidate(
        self,
        session: AsyncSession,
        record: RegenerationStateRecord,
        source_revision_hash: str,
    ) -> RegenerationStateRecord:
        state = RegenerationState(
            artifact_id=record.artifact_version_id,
            source_revision_hash=record.source_revision_hash,
            status=record.status,  # type: ignore[arg-type]
            output_revision_hash=record.output_revision_hash,
        )
        next_state = invalidate(state, source_revision_hash)
        record.source_revision_hash = next_state.source_revision_hash
        record.status = next_state.status
        record.output_revision_hash = next_state.output_revision_hash
        await session.flush()
        return record
