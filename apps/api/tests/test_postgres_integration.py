"""PostgreSQL/PostGIS integration gate for CI and local database validation."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_postgres_postgis_and_schema_are_available() -> None:
    """Exercise the actual deployed database dialect rather than SQLite emulation."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("postgresql+asyncpg://"):
        pytest.skip("PostgreSQL/PostGIS integration requires DATABASE_URL")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            database = (await connection.execute(text("SELECT current_database()"))).scalar_one()
            postgis = (await connection.execute(text("SELECT PostGIS_Version()"))).scalar_one()
            revision = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one()
            tables = {
                row[0]
                for row in (
                    await connection.execute(
                        text(
                            """
                            SELECT table_name
                            FROM information_schema.tables
                            WHERE table_schema = 'public'
                            """
                        )
                    )
                ).all()
            }
    finally:
        await engine.dispose()

    assert database == "building_test"
    assert postgis
    assert revision
    assert {"organizations", "projects", "project_versions"}.issubset(tables)
