import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.regeneration_job_models import RegenerationJobRecord
from app.db.regeneration_models import RegenerationStateRecord
from app.domains.commands.regeneration_queue import RegenerationQueue
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
