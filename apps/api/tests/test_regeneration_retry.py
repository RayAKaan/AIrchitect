from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.regeneration_job_models import RegenerationJobRecord
from app.db.regeneration_models import RegenerationStateRecord
from app.domains.commands.regeneration_queue import RegenerationQueue
from app.domains.commands.regeneration_repository import RegenerationStateRepository


@pytest.mark.asyncio
async def test_failed_job_is_requeued_until_attempt_limit() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(RegenerationStateRecord.__table__.create)
        await connection.run_sync(RegenerationJobRecord.__table__.create)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    states = RegenerationStateRepository()
    queue = RegenerationQueue(states)
    async with sessions() as session:
        state = await states.create_invalidated(
            session,
            organization_id="org",
            project_id="project",
            project_version_id="version",
            artifact_version_id="artifact",
            source_revision_hash="rev-2",
            generation_key="geometry:rev-2",
        )
        job = await queue.enqueue(session, state, max_attempts=2)
        await queue.claim_next(session, worker_id="worker-1")
        await queue.fail(session, job, error_code="engine_error", error_message="boom")
        assert job.status == "QUEUED"
        assert state.status == "QUEUED"
        assert job.attempt_count == 1
        assert job.available_at > job.created_at

        # Force the retry to be immediately claimable without waiting for backoff.
        job.available_at = job.created_at
        await queue.claim_next(session, worker_id="worker-2")
        await queue.fail(session, job, error_code="engine_error", error_message="boom again")
        assert job.status == "FAILED"
        assert state.status == "FAILED"
        await session.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_expired_lease_is_recovered() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(RegenerationStateRecord.__table__.create)
        await connection.run_sync(RegenerationJobRecord.__table__.create)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    states = RegenerationStateRepository()
    queue = RegenerationQueue(states)
    async with sessions() as session:
        state = await states.create_invalidated(
            session,
            organization_id="org",
            project_id="project",
            project_version_id="version",
            artifact_version_id="artifact",
            source_revision_hash="rev-2",
            generation_key="geometry:rev-2",
        )
        job = await queue.enqueue(session, state)
        await queue.claim_next(session, worker_id="worker-1")
        job.locked_at = job.created_at - timedelta(hours=1)
        recovered = await queue.recover_expired_leases(session, lease_timeout=timedelta(minutes=5))
        assert recovered == (job.id,)
        assert job.status == "QUEUED"
        assert state.status == "QUEUED"
        await session.commit()

    await engine.dispose()
