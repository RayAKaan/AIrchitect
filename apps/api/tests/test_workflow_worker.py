from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, WorkflowRecord, WorkflowTaskRecord
from app.domains.lifecycle.workflow_worker import (
    TaskExecutionResult,
    WorkflowTaskHandlerRegistry,
    WorkflowWorker,
)


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


async def _task(session, *, key: str, max_attempts: int = 1):
    workflow = WorkflowRecord(
        organization_id="org",
        project_id="project",
        project_version_id="version",
        created_by="user",
        workflow_type="test",
        idempotency_key=f"workflow-{key}",
    )
    session.add(workflow)
    await session.flush()
    task = WorkflowTaskRecord(
        workflow_id=workflow.id,
        key=key,
        kind=key,
        payload_json={"value": 7},
        max_attempts=max_attempts,
    )
    session.add(task)
    await session.flush()
    await session.commit()
    return task


@pytest.mark.asyncio
async def test_worker_executes_registered_handler_and_commits_result(session_factory):
    async with session_factory() as session:
        task = await _task(session, key="success")
        calls: list[str] = []

        async def handler(open_session, task_id: str, payload: dict) -> TaskExecutionResult:
            calls.append(task_id)
            assert payload == {"value": 7}
            return TaskExecutionResult(result={"answer": 14}, output_hash="a" * 64)

        registry = WorkflowTaskHandlerRegistry({"success": handler})
        result = await WorkflowWorker(worker_id="worker-a", handlers=registry).run_once(session)

        assert result.status == "SUCCEEDED"
        assert result.task_id == task.id
        assert calls == [task.id]
        refreshed = await session.get(WorkflowTaskRecord, task.id)
        assert refreshed is not None
        assert refreshed.state == "succeeded"
        assert refreshed.output_hash == "a" * 64
        assert refreshed.owner is None


@pytest.mark.asyncio
async def test_worker_rolls_back_handler_failure_before_recording_failure(session_factory):
    async with session_factory() as session:
        task = await _task(session, key="failure")

        async def handler(open_session, task_id: str, payload: dict) -> TaskExecutionResult:
            open_session.add(
                WorkflowTaskRecord(
                    workflow_id=task.workflow_id,
                    key="partial",
                    kind="partial",
                    payload_json={"must_not_persist": True},
                )
            )
            await open_session.flush()
            raise RuntimeError("handler exploded")

        registry = WorkflowTaskHandlerRegistry({"failure": handler})
        result = await WorkflowWorker(worker_id="worker-a", handlers=registry).run_once(session)

        assert result.status == "FAILED"
        refreshed = await session.get(WorkflowTaskRecord, task.id)
        assert refreshed is not None
        assert refreshed.state == "failed"
        assert refreshed.error_code == "runtimeerror"
        partial = await session.get(WorkflowTaskRecord, "does-not-exist")
        assert partial is None
