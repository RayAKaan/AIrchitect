from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WorkflowRecord, WorkflowTaskRecord
from app.db.regeneration_job_models import RegenerationJobRecord


@dataclass(frozen=True)
class QueueMetrics:
    queued: int = 0
    running: int = 0
    failed: int = 0
    retried: int = 0
    expired_leases: int = 0
    oldest_queued_at: datetime | None = None


@dataclass(frozen=True)
class RuntimeMetrics:
    workflow: QueueMetrics
    regeneration: QueueMetrics

    def as_dict(self) -> dict[str, dict[str, object]]:
        return {"workflow": asdict(self.workflow), "regeneration": asdict(self.regeneration)}


async def collect_runtime_metrics(
    session: AsyncSession,
    *,
    organization_id: str | None = None,
    regeneration_lease_timeout: timedelta = timedelta(minutes=5),
) -> RuntimeMetrics:
    if regeneration_lease_timeout <= timedelta(0):
        raise ValueError("regeneration_lease_timeout must be positive")
    now = datetime.now(timezone.utc)
    workflow = await _collect_workflow(session, organization_id=organization_id, now=now)
    regeneration = await _collect_regeneration(
        session,
        organization_id=organization_id,
        now=now,
        lease_timeout=regeneration_lease_timeout,
    )
    return RuntimeMetrics(workflow=workflow, regeneration=regeneration)


async def _collect_workflow(session: AsyncSession, *, organization_id: str | None, now: datetime) -> QueueMetrics:
    scope = [] if organization_id is None else [WorkflowRecord.organization_id == organization_id]
    counts = dict(
        (
            await session.execute(
                select(WorkflowTaskRecord.state, func.count())
                .join(WorkflowRecord, WorkflowRecord.id == WorkflowTaskRecord.workflow_id)
                .where(*scope)
                .group_by(WorkflowTaskRecord.state)
            )
        ).all()
    )
    retried = await session.scalar(
        select(func.count())
        .select_from(WorkflowTaskRecord)
        .join(WorkflowRecord, WorkflowRecord.id == WorkflowTaskRecord.workflow_id)
        .where(WorkflowTaskRecord.attempts > 1, *scope)
    ) or 0
    expired = await session.scalar(
        select(func.count())
        .select_from(WorkflowTaskRecord)
        .join(WorkflowRecord, WorkflowRecord.id == WorkflowTaskRecord.workflow_id)
        .where(
            WorkflowTaskRecord.state == "running",
            WorkflowTaskRecord.lease_expires_at.is_not(None),
            WorkflowTaskRecord.lease_expires_at <= now,
            *scope,
        )
    ) or 0
    oldest = await session.scalar(
        select(func.min(WorkflowTaskRecord.available_at))
        .join(WorkflowRecord, WorkflowRecord.id == WorkflowTaskRecord.workflow_id)
        .where(WorkflowTaskRecord.state == "pending", *scope)
    )
    return QueueMetrics(
        queued=int(counts.get("pending", 0)),
        running=int(counts.get("running", 0)),
        failed=int(counts.get("failed", 0)),
        retried=int(retried),
        expired_leases=int(expired),
        oldest_queued_at=oldest,
    )


async def _collect_regeneration(
    session: AsyncSession,
    *,
    organization_id: str | None,
    now: datetime,
    lease_timeout: timedelta,
) -> QueueMetrics:
    scope = [] if organization_id is None else [RegenerationJobRecord.organization_id == organization_id]
    cutoff = now - lease_timeout
    counts = dict(
        (
            await session.execute(
                select(RegenerationJobRecord.status, func.count())
                .where(*scope)
                .group_by(RegenerationJobRecord.status)
            )
        ).all()
    )
    retried = await session.scalar(
        select(func.count()).select_from(RegenerationJobRecord).where(RegenerationJobRecord.attempt_count > 1, *scope)
    ) or 0
    expired = await session.scalar(
        select(func.count()).select_from(RegenerationJobRecord).where(
            RegenerationJobRecord.status == "RUNNING",
            RegenerationJobRecord.locked_at.is_not(None),
            RegenerationJobRecord.locked_at < cutoff,
            *scope,
        )
    ) or 0
    oldest = await session.scalar(
        select(func.min(RegenerationJobRecord.available_at)).where(
            RegenerationJobRecord.status == "QUEUED", *scope
        )
    )
    return QueueMetrics(
        queued=int(counts.get("QUEUED", 0)),
        running=int(counts.get("RUNNING", 0)),
        failed=int(counts.get("FAILED", 0)),
        retried=int(retried),
        expired_leases=int(expired),
        oldest_queued_at=oldest,
    )
