from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, WorkflowEvent, WorkflowRecord, WorkflowTaskRecord
from app.domains.lifecycle.workflow_queue import WorkflowTaskQueue


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _task(session, *, key: str, depends_on: list[str] | None = None, max_attempts: int = 3):
    workflow = await session.scalar(select(WorkflowRecord).limit(1))
    if workflow is None:
        workflow = WorkflowRecord(
            organization_id="org",
            project_id="project",
            project_version_id="version",
            created_by="user",
            workflow_type="test",
            idempotency_key="test-workflow",
        )
        session.add(workflow)
        await session.flush()
    task = WorkflowTaskRecord(
        workflow_id=workflow.id,
        key=key,
        kind=key,
        payload_json={},
        depends_on_json=depends_on or [],
        max_attempts=max_attempts,
    )
    session.add(task)
    await session.flush()
    return task


@pytest.mark.asyncio
async def test_claim_respects_dependencies_and_records_lease(session_factory):
    async with session_factory() as session:
        first = await _task(session, key="first")
        second = await _task(session, key="second", depends_on=[first.id])
        await session.commit()

        queue = WorkflowTaskQueue()
        claimed = await queue.claim_next(session, worker_id="worker-a")
        assert claimed is not None
        assert claimed.id == first.id
        assert claimed.state == "running"
        assert claimed.owner == "worker-a"
        assert claimed.attempts == 1
        assert claimed.lease_expires_at is not None

        await session.commit()
        assert await queue.claim_next(session, worker_id="worker-b") is None

        await queue.complete(session, first.id, worker_id="worker-a", result={"ok": True}, output_hash="a" * 64)
        await session.commit()

        claimed = await queue.claim_next(session, worker_id="worker-b")
        assert claimed is not None
        assert claimed.id == second.id

        events = list((await session.scalars(select(WorkflowEvent).order_by(WorkflowEvent.created_at))).all())
        assert [(event.from_state, event.to_state) for event in events] == [
            ("pending", "running"),
            ("running", "succeeded"),
            ("pending", "running"),
        ]


@pytest.mark.asyncio
async def test_heartbeat_requires_current_owner(session_factory):
    async with session_factory() as session:
        task = await _task(session, key="heartbeat")
        await session.commit()
        queue = WorkflowTaskQueue()
        await queue.claim_next(session, worker_id="worker-a")
        await session.commit()

        with pytest.raises(ValueError, match="owned by another worker"):
            await queue.heartbeat(session, task.id, worker_id="worker-b")

        updated = await queue.heartbeat(session, task.id, worker_id="worker-a", lease_timeout=timedelta(minutes=2))
        assert updated.heartbeat_at is not None
        assert updated.lease_expires_at is not None


@pytest.mark.asyncio
async def test_failure_requeues_until_attempt_ceiling(session_factory):
    async with session_factory() as session:
        task = await _task(session, key="retry", max_attempts=2)
        await session.commit()
        queue = WorkflowTaskQueue()

        await queue.claim_next(session, worker_id="worker-a")
        await queue.fail(
            session,
            task.id,
            worker_id="worker-a",
            error_code="TEMPORARY",
            error_message="temporary failure",
        )
        assert task.state == "pending"
        assert task.attempts == 1
        assert task.available_at is not None
        await session.commit()

        task.available_at = task.available_at - timedelta(minutes=10)
        await session.commit()
        await queue.claim_next(session, worker_id="worker-b")
        await queue.fail(
            session,
            task.id,
            worker_id="worker-b",
            error_code="PERMANENT",
            error_message="permanent failure",
        )
        assert task.state == "failed"
        assert task.attempts == 2
        assert task.completed_at is not None
