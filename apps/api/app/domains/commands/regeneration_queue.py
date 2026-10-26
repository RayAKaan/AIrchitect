from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.regeneration_job_models import RegenerationJobRecord
from app.db.regeneration_models import RegenerationStateRecord

from .regeneration_repository import RegenerationStateRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _retry_delay(attempt_count: int) -> timedelta:
    return timedelta(seconds=min(300, 5 * (2 ** max(0, attempt_count - 1))))


class RegenerationQueue:
    """Durable queue adapter with idempotent enqueue, claims, retries, and leases."""

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

        state_result = await session.execute(
            select(RegenerationStateRecord)
            .where(RegenerationStateRecord.id == job.regeneration_state_id)
            .with_for_update()
        )
        regeneration_state = state_result.scalar_one()
        if regeneration_state.status != "QUEUED":
            raise ValueError("queued job does not reference a QUEUED regeneration state")
        await self._states.transition(session, regeneration_state, "RUNNING")

        job.status = "RUNNING"
        job.attempt_count += 1
        job.locked_at = _now()
        job.locked_by = worker_id
        await session.flush()
        return job

    async def fail(
        self,
        session: AsyncSession,
        job: RegenerationJobRecord,
        *,
        error_code: str,
        error_message: str,
    ) -> RegenerationJobRecord:
        if job.status != "RUNNING":
            raise ValueError(f"cannot fail job in {job.status} status")
        state_result = await session.execute(
            select(RegenerationStateRecord)
            .where(RegenerationStateRecord.id == job.regeneration_state_id)
            .with_for_update()
        )
        state = state_result.scalar_one()
        if state.status != "RUNNING":
            raise ValueError(f"running job has non-running state: {state.status}")

        await self._states.transition(session, state, "FAILED")
        job.error_code = error_code[:100]
        job.error_message = error_message[:2000]
        job.locked_at = None
        job.locked_by = None
        if job.attempt_count < job.max_attempts:
            await self._states.transition(session, state, "QUEUED")
            job.status = "QUEUED"
            job.available_at = _now() + _retry_delay(job.attempt_count)
        else:
            job.status = "FAILED"
            job.completed_at = _now()
        await session.flush()
        return job

    async def recover_expired_leases(
        self,
        session: AsyncSession,
        *,
        lease_timeout: timedelta,
    ) -> tuple[str, ...]:
        if lease_timeout <= timedelta(0):
            raise ValueError("lease_timeout must be positive")
        cutoff = _now() - lease_timeout
        result = await session.execute(
            select(RegenerationJobRecord)
            .where(
                RegenerationJobRecord.status == "RUNNING",
                RegenerationJobRecord.locked_at.is_not(None),
                RegenerationJobRecord.locked_at < cutoff,
            )
            .order_by(RegenerationJobRecord.locked_at, RegenerationJobRecord.id)
            .with_for_update(skip_locked=True)
        )
        recovered: list[str] = []
        for job in result.scalars():
            await self.fail(
                session,
                job,
                error_code="worker_lease_expired",
                error_message="worker lease expired before regeneration completed",
            )
            recovered.append(job.id)
        await session.flush()
        return tuple(recovered)
