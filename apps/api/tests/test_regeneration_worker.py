import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.regeneration_job_models import RegenerationJobRecord
from app.db.regeneration_models import RegenerationStateRecord
from app.domains.commands.regeneration_queue import RegenerationQueue
from app.domains.commands.regeneration_repository import RegenerationStateRepository
from app.domains.commands.regeneration_worker import RegenerationWorker


class FailingService:
    async def execute_job(self, session, job_id, *, worker_id, attempt_count):
        raise RuntimeError("deterministic test failure")


@pytest.mark.asyncio
async def test_worker_rolls_back_partial_execution_and_records_retryable_failure() -> None:
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
        await session.commit()

        result = await RegenerationWorker(
            worker_id="worker-1",
            queue=queue,
            service=FailingService(),
        ).run_once(session)
        assert result.status == "FAILED"
        assert result.job_id == job.id
        assert result.error_code == "runtimeerror"

        refreshed_job = await session.get(RegenerationJobRecord, job.id)
        refreshed_state = await session.get(RegenerationStateRecord, state.id)
        assert refreshed_job is not None
        assert refreshed_state is not None
        assert refreshed_job.status == "QUEUED"
        assert refreshed_job.attempt_count == 1
        assert refreshed_state.status == "QUEUED"

    await engine.dispose()
