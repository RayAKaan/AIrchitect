"""PostgreSQL/PostGIS integration gate for CI and local database validation."""

from __future__ import annotations

import asyncio
import os
import uuid

import httpx

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.session import get_session
from app.core.config import settings
from app.main import app


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


@pytest.mark.asyncio
async def test_postgres_tenant_isolation_and_concurrent_project_updates() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("postgresql+asyncpg://"):
        pytest.skip("PostgreSQL tenant-isolation integration requires DATABASE_URL")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://postgres-test") as client:
            async def create_user(suffix: str):
                response = await client.post("/api/v1/auth/register", json={
                    "email": suffix + "-" + uuid.uuid4().hex + "@example.com",
                    "name": suffix,
                    "password": "a-very-secure-password",
                    "organization_name": suffix + " Org",
                })
                assert response.status_code == 201, response.text
                headers = {"Authorization": "Bearer " + response.json()["access_token"]}
                organization = (await client.get("/api/v1/organizations", headers=headers)).json()[0]
                return headers, organization

            owner_headers, organization = await create_user("pg-owner")
            foreign_headers, _ = await create_user("pg-foreign")
            created = await client.post("/api/v1/projects", headers=owner_headers, json={
                "organization_id": organization["id"], "name": "PostgreSQL isolation", "description": "Version 1"
            })
            assert created.status_code == 201, created.text
            project_id = created.json()["id"]
            assert created.headers["etag"] == '"1"'

            assert (await client.get("/api/v1/projects/" + project_id, headers=foreign_headers)).status_code == 404
            assert (await client.get("/api/v1/projects", headers=foreign_headers,
                params={"organization_id": organization["id"]})).status_code == 404
            foreign_update = await client.patch("/api/v1/projects/" + project_id,
                headers={**foreign_headers, "If-Match": '"1"'}, json={
                    "organization_id": organization["id"], "name": "Unauthorized", "description": "Must not persist"
                })
            assert foreign_update.status_code == 404

            async def update_project(name: str):
                return await client.patch("/api/v1/projects/" + project_id,
                    headers={**owner_headers, "If-Match": '"1"'}, json={
                        "organization_id": organization["id"], "name": name, "description": "Concurrent write"
                    })

            results = await asyncio.gather(update_project("Concurrent A"), update_project("Concurrent B"))
            assert sorted(result.status_code for result in results) == [200, 412]
            current = await client.get("/api/v1/projects/" + project_id, headers=owner_headers)
            assert current.status_code == 200
            assert current.json()["version"] == 2
            assert current.headers["etag"] == '"2"'
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_password_reset_requests_are_serialized_per_user(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("postgresql+asyncpg://"):
        pytest.skip("PostgreSQL identity-token concurrency requires DATABASE_URL")

    sent: list[str] = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_sender", "noreply@example.test")
    import app.main as main
    monkeypatch.setattr(main, "send_email", lambda recipient, subject, body: sent.append(recipient))

    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://postgres-test") as client:
            email = "pg-reset-" + uuid.uuid4().hex + "@example.com"
            registered = await client.post("/api/v1/auth/register", json={
                "email": email, "name": "Postgres Reset", "password": "a-very-secure-password",
                "organization_name": "Postgres Reset Org",
            })
            assert registered.status_code == 201, registered.text

            first, second = await asyncio.gather(
                client.post("/api/v1/auth/forgot-password", json={"email": email}),
                client.post("/api/v1/auth/forgot-password", json={"email": email}),
            )
            assert first.status_code == second.status_code == 200
            assert first.json()["message"] == second.json()["message"]
            assert sent == [email]
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
