from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WorkflowEvent, WorkflowTaskRecord


PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"

_RETRY_BASE_SECONDS = 5
_RETRY_MAX_SECONDS = 300
_DEFAULT_LEASE = timedelta(minutes=5)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _retry_delay(attempts: int) -> timedelta:
    return timedelta(seconds=min(_RETRY_MAX_SECONDS, _RETRY_BASE_SECONDS * (2 ** max(0, attempts - 1))))


def _transition_allowed(source: str, target: str) -> bool:
    return (source, target) in {
        (PENDING, RUNNING),
        (RUNNING, SUCCEEDED),
        (RUNNING, FAILED),
        (FAILED, PENDING),
        (RUNNING, PENDING),
    }


class WorkflowTaskQueue:
    """Transactional queue for persisted workflow tasks.

    Workflow tasks are intentionally separate from regeneration jobs: the workflow
    graph orchestrates a computation, while regeneration is the artifact-runtime
    boundary. This queue only owns task lifecycle, leases and retries.
    """

    async def claim_next(
        self,
        session: AsyncSession,
        *,
        worker_id: str,
        lease_timeout: timedelta = _DEFAULT_LEASE,
        candidate_limit: int = 50,
    ) -> WorkflowTaskRecord | None:
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        if lease_timeout <= timedelta(0):
            raise ValueError("lease_timeout must be positive")
        if candidate_limit < 1:
            raise ValueError("candidate_limit must be positive")

        candidates = list(
            (
                await session.scalars(
                    select(WorkflowTaskRecord)
                    .where(
                        WorkflowTaskRecord.state == PENDING,
                        WorkflowTaskRecord.available_at <= _now(),
                    )
                    .order_by(
                        WorkflowTaskRecord.available_at,
                        WorkflowTaskRecord.created_at,
                        WorkflowTaskRecord.id,
                    )
                    .limit(candidate_limit)
                )
            ).all()
        )

        for candidate in candidates:
            if not await self._dependencies_succeeded(session, candidate):
                continue
            result = await session.execute(
                select(WorkflowTaskRecord)
                .where(
                    WorkflowTaskRecord.id == candidate.id,
                    WorkflowTaskRecord.state == PENDING,
                )
                .with_for_update(skip_locked=True)
            )
            task = result.scalar_one_or_none()
            if task is None:
                continue
            if not await self._dependencies_succeeded(session, task):
                continue
            await self._transition(session, task, RUNNING, worker_id=worker_id)
            task.attempts += 1
            task.owner = worker_id
            task.started_at = _now()
            task.heartbeat_at = task.started_at
            task.lease_expires_at = task.started_at + lease_timeout
            await session.flush()
            return task
        return None

    async def heartbeat(
        self,
        session: AsyncSession,
        task_id: str,
        *,
        worker_id: str,
        lease_timeout: timedelta = _DEFAULT_LEASE,
    ) -> WorkflowTaskRecord:
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        if lease_timeout <= timedelta(0):
            raise ValueError("lease_timeout must be positive")
        task = await self._locked_task(session, task_id)
        if task.state != RUNNING:
            raise ValueError(f"cannot heartbeat task in {task.state} state")
        if task.owner != worker_id:
            raise ValueError("workflow task lease is owned by another worker")
        now = _now()
        if task.lease_expires_at is not None and task.lease_expires_at <= now:
            raise ValueError("workflow task lease has expired")
        task.heartbeat_at = now
        task.lease_expires_at = now + lease_timeout
        await session.flush()
        return task

    async def complete(
        self,
        session: AsyncSession,
        task_id: str,
        *,
        worker_id: str,
        result: dict,
        output_hash: str,
        artifact_version_id: str | None = None,
    ) -> WorkflowTaskRecord:
        task = await self._locked_task(session, task_id)
        self._assert_owner(task, worker_id)
        await self._transition(session, task, SUCCEEDED, worker_id=worker_id)
        task.result_json = result
        task.output_hash = output_hash
        task.artifact_version_id = artifact_version_id
        task.completed_at = _now()
        self._clear_lease(task)
        await session.flush()
        return task

    async def fail(
        self,
        session: AsyncSession,
        task_id: str,
        *,
        worker_id: str,
        error_code: str,
        error_message: str,
        failure_class: str = "transient",
    ) -> WorkflowTaskRecord:
        task = await self._locked_task(session, task_id)
        self._assert_owner(task, worker_id)
        await self._transition(session, task, FAILED, worker_id=worker_id)
        task.error_code = error_code[:100]
        task.error_message = error_message[:4000]
        task.failure_class = failure_class[:32]
        self._clear_lease(task)
        if task.attempts < task.max_attempts:
            await self._transition(session, task, PENDING, worker_id=worker_id)
            task.available_at = _now() + _retry_delay(task.attempts)
        else:
            task.completed_at = _now()
        await session.flush()
        return task

    async def recover_expired_leases(
        self,
        session: AsyncSession,
        *,
        limit: int = 100,
    ) -> tuple[str, ...]:
        if limit < 1:
            raise ValueError("limit must be positive")
        now = _now()
        result = await session.execute(
            select(WorkflowTaskRecord)
            .where(
                WorkflowTaskRecord.state == RUNNING,
                WorkflowTaskRecord.lease_expires_at.is_not(None),
                WorkflowTaskRecord.lease_expires_at <= now,
            )
            .order_by(WorkflowTaskRecord.lease_expires_at, WorkflowTaskRecord.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        recovered: list[str] = []
        for task in result.scalars():
            await self._transition(session, task, FAILED, worker_id=task.owner or "system")
            task.failure_class = "lease_expired"
            task.error_code = "workflow_lease_expired"
            task.error_message = "workflow task lease expired before completion"
            self._clear_lease(task)
            if task.attempts < task.max_attempts:
                await self._transition(session, task, PENDING, worker_id="system")
                task.available_at = now + _retry_delay(task.attempts)
            else:
                task.completed_at = now
            recovered.append(task.id)
        await session.flush()
        return tuple(recovered)

    async def _dependencies_succeeded(self, session: AsyncSession, task: WorkflowTaskRecord) -> bool:
        dependency_ids = task.depends_on_json or []
        if not dependency_ids:
            return True
        states = list(
            (
                await session.scalars(
                    select(WorkflowTaskRecord.state).where(WorkflowTaskRecord.id.in_(dependency_ids))
                )
            ).all()
        )
        return len(states) == len(dependency_ids) and all(state == SUCCEEDED for state in states)

    async def _locked_task(self, session: AsyncSession, task_id: str) -> WorkflowTaskRecord:
        result = await session.execute(
            select(WorkflowTaskRecord).where(WorkflowTaskRecord.id == task_id).with_for_update()
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise ValueError("workflow task not found")
        return task

    async def _transition(
        self,
        session: AsyncSession,
        task: WorkflowTaskRecord,
        target: str,
        *,
        worker_id: str,
    ) -> None:
        if not _transition_allowed(task.state, target):
            raise ValueError(f"illegal workflow task transition: {task.state} -> {target}")
        session.add(
            WorkflowEvent(
                workflow_id=task.workflow_id,
                task_id=task.id,
                event_type="workflow_task.transition",
                from_state=task.state,
                to_state=target,
                data_json={"worker_id": worker_id},
            )
        )
        task.state = target

    @staticmethod
    def _assert_owner(task: WorkflowTaskRecord, worker_id: str) -> None:
        if task.state != RUNNING:
            raise ValueError(f"workflow task is not running: {task.state}")
        if task.owner != worker_id:
            raise ValueError("workflow task lease is owned by another worker")

    @staticmethod
    def _clear_lease(task: WorkflowTaskRecord) -> None:
        task.owner = None
        task.lease_expires_at = None
        task.heartbeat_at = None
