from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.regeneration_models import RegenerationStateRecord

from .regeneration_state import RegenerationState, RegenerationStatus, invalidate


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

    async def create_invalidated(
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
            status="INVALIDATED",
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
        state = self._domain_state(record)
        next_state = invalidate(state, source_revision_hash)
        self._apply(record, next_state)
        await session.flush()
        return record

    async def transition(
        self,
        session: AsyncSession,
        record: RegenerationStateRecord,
        status: RegenerationStatus,
        *,
        output_revision_hash: str | None = None,
    ) -> RegenerationStateRecord:
        state = self._domain_state(record)
        next_state = state.transition(status, output_revision_hash=output_revision_hash)
        self._apply(record, next_state)
        await session.flush()
        return record

    @staticmethod
    def _domain_state(record: RegenerationStateRecord) -> RegenerationState:
        return RegenerationState(
            artifact_id=record.artifact_version_id,
            source_revision_hash=record.source_revision_hash,
            status=cast(RegenerationStatus, record.status),
            output_revision_hash=record.output_revision_hash,
        )

    @staticmethod
    def _apply(record: RegenerationStateRecord, state: RegenerationState) -> None:
        record.source_revision_hash = state.source_revision_hash
        record.status = state.status
        record.output_revision_hash = state.output_revision_hash
