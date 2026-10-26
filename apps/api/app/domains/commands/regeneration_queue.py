from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.regeneration_job_models import RegenerationJobRecord
from app.db.regeneration_models import RegenerationStateRecord

from .regeneration_repository import RegenerationStateRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RegenerationQueue:
    """Durable queue adapter with idempotent enqueue and transactional claims."""

    def __init__(self, repository: RegenerationStateRepository | None = None) -> None:
        self._states = repository or RegenerationStateRepository()

    async def enqueue(
        self,
        session: AsyncSession,
        state: RegenerationStateRecord,
        *,
        max_attempts: int = 3,
    ) -> RegenerationJobRecord:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        locked_state = await self._states.get_for_update(session, state.artifact_version_id)
        if locked_state is None:
            raise ValueError("regeneration state does not exist")
        if locked_state.id != state.id:
            raise ValueError("regeneration state changed while enqueueing")

        if locked_state.status == "INVALIDATED":
            await self._states.transition(session, locked_state, "STALE")
            await self._states.transition(session, locked_state, "QUEUED")
        elif locked_state.status != "QUEUED":
            raise ValueError(f"cannot enqueue regeneration state in {locked_state.status} status")

        existing = await session.execute(
            select(RegenerationJobRecord).where(
                RegenerationJobRecord.regeneration_state_id == locked_state.id,
                RegenerationJobRecord.source_revision_hash == locked_state.source_revision_hash,
            )
        )
        job = existing.scalar_one_or_none()
        if job is not None:
            return job

        job = RegenerationJobRecord(
            regeneration_state_id=locked_state.id,
            organization_id=locked_state.organization_id,
            project_id=locked_state.project_id,
            project_version_id=locked_state.project_version_id,
            artifact_version_id=locked_state.artifact_version_id,
            source_revision_hash=locked_state.source_revision_hash,
            status="QUEUED",
            max_attempts=max_attempts,
            metadata_json={"enqueue_token": str(uuid4())},
        )
        session.add(job)
        await session.flush()
        return job

    async def claim_next(
        self,
        session: AsyncSession,
        *,
        worker_id: str,
    ) -> RegenerationJobRecord | None:
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        result = await session.execute(
            select(RegenerationJobRecord)
            .where(
                RegenerationJobRecord.status == "QUEUED",
                RegenerationJobRecord.available_at <= _now(),
            )
            .order_by(RegenerationJobRecord.available_at, RegenerationJobRecord.created_at, RegenerationJobRecord.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None

        state = await session.execute(
            select(RegenerationStateRecord)
            .where(RegenerationStateRecord.id == job.regeneration_state_id)
            .with_for_update()
        )
        regeneration_state = state.scalar_one()
        if regeneration_state.status != "QUEUED":
            raise ValueError("queued job does not reference a QUEUED regeneration state")
        await self._states.transition(session, regeneration_state, "RUNNING")

        job.status = "RUNNING"
        job.attempt_count += 1
        job.locked_at = _now()
        job.locked_by = worker_id
        await session.flush()
        return job
