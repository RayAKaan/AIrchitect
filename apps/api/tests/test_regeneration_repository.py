import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.regeneration_models import RegenerationStateRecord
from app.domains.commands.regeneration_repository import RegenerationStateRepository


@pytest.mark.asyncio
async def test_regeneration_repository_persists_and_invalidates_state() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(RegenerationStateRecord.__table__.create)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repository = RegenerationStateRepository()
    async with sessions() as session:
        await repository.create_current(
            session,
            organization_id="org",
            project_id="project",
            project_version_id="version",
            artifact_version_id="artifact",
            source_revision_hash="rev-1",
            generation_key="geometry:1",
        )
        await session.commit()

        loaded = await repository.get_for_update(session, "artifact")
        assert loaded is not None
        assert loaded.status == "CURRENT"
        assert loaded.output_revision_hash == "rev-1"

        await repository.invalidate(session, loaded, "rev-2")
        assert loaded.status == "INVALIDATED"
        assert loaded.source_revision_hash == "rev-2"
        assert loaded.output_revision_hash is None
        await session.commit()

    await engine.dispose()
