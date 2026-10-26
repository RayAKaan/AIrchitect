from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, WorkflowRecord, WorkflowTaskRecord
from app.db.regeneration_job_models import RegenerationJobRecord
from app.domains.lifecycle.runtime_observability import collect_runtime_metrics


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


@pytest.mark.asyncio
async def test_runtime_metrics_count_queue_states(session_factory):
    async with session_factory() as session:
        workflow = WorkflowRecord(
            organization_id="org",
            project_id="project",
            project_version_id="version",
            created_by="user",
            workflow_type="test",
            idempotency_key="metrics",
        )
        session.add(workflow)
        await session.flush()
        session.add_all(
            [
                WorkflowTaskRecord(
                    workflow_id=workflow.id,
                    key="queued",
                    kind="test",
                    payload_json={},
                    state="pending",
                ),
                WorkflowTaskRecord(
                    workflow_id=workflow.id,
                    key="running",
                    kind="test",
                    payload_json={},
                    state="running",
                    lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                ),
                WorkflowTaskRecord(
                    workflow_id=workflow.id,
                    key="failed",
                    kind="test",
                    payload_json={},
                    state="failed",
                    attempts=2,
                ),
            ]
        )
        session.add(
            RegenerationJobRecord(
                regeneration_state_id="state",
                organization_id="org",
                project_id="project",
                project_version_id="version",
                artifact_version_id="artifact",
                source_revision_hash="a" * 64,
                status="RUNNING",
                attempt_count=2,
                locked_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            )
        )
        await session.commit()

        metrics = await collect_runtime_metrics(session, organization_id="org")
        assert metrics.workflow.queued == 1
        assert metrics.workflow.running == 1
        assert metrics.workflow.failed == 1
        assert metrics.workflow.retried == 1
        assert metrics.workflow.expired_leases == 1
        assert metrics.regeneration.running == 1
        assert metrics.regeneration.retried == 1
        assert metrics.regeneration.expired_leases == 1
