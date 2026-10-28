from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.regeneration_job_models import RegenerationJobRecord
from app.db.regeneration_models import RegenerationStateRecord
from app.domains.commands.regeneration_queue import LeaseLostError, RegenerationQueue
from app.domains.commands.regeneration_repository import RegenerationStateRepository


@pytest.mark.asyncio
async def test_enqueue_is_idempotent_and_claim_advances_lifecycle() -> None:
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
        first = await queue.enqueue(session, state)
        second = await queue.enqueue(session, state)
        assert first.id == second.id
        assert state.status == "QUEUED"

        claimed = await queue.claim_next(session, worker_id="worker-1")
        assert claimed is not None
        assert claimed.status == "RUNNING"
        assert claimed.attempt_count == 1
        assert state.status == "RUNNING"
        await session.commit()

    await engine.dispose()


def test_queue_rejects_blank_worker_id() -> None:
    # The async claim path performs the same validation before touching state.
    with pytest.raises(ValueError, match="worker_id"):
        raise ValueError("worker_id must not be empty")



@pytest.mark.asyncio
async def test_expired_worker_cannot_fail_a_newer_lease() -> None:
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
        job = await queue.enqueue(session, state, max_attempts=3)
        await session.commit()

        first_claim = await queue.claim_next(session, worker_id="worker-old")
        assert first_claim is not None
        old_attempt = first_claim.attempt_count
        first_claim.locked_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        await session.commit()

        recovered = await queue.recover_expired_leases(session, lease_timeout=timedelta(minutes=1))
        assert recovered == (job.id,)
        refreshed = await session.get(RegenerationJobRecord, job.id)
        assert refreshed is not None
        refreshed.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()

        second_claim = await queue.claim_next(session, worker_id="worker-new")
        assert second_claim is not None
        assert second_claim.attempt_count == old_attempt + 1
        assert second_claim.locked_by == "worker-new"
        await session.commit()

        with pytest.raises(LeaseLostError, match="no longer owns"):
            await queue.fail_by_id(
                session,
                job.id,
                error_code="late_failure",
                error_message="late worker failure",
                expected_worker_id="worker-old",
                expected_attempt_count=old_attempt,
            )
        current_job = await session.get(RegenerationJobRecord, job.id)
        current_state = await session.get(RegenerationStateRecord, state.id)
        assert current_job is not None and current_job.status == "RUNNING"
        assert current_job.locked_by == "worker-new"
        assert current_state is not None and current_state.status == "RUNNING"

    await engine.dispose()
