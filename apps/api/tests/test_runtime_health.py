import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.models import Base
from app.domains.lifecycle.runtime_health import check_runtime_health


@pytest.mark.asyncio
async def test_runtime_health_reports_database_ready():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with engine.connect() as connection:
        health = await check_runtime_health(connection)
    assert health.ready is True
    await engine.dispose()
