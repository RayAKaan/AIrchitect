from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import ArtifactDependency, ArtifactVersion, Base, Project, ProjectVersion, User, WorldModelRevision
from app.domains.lifecycle.artifact_rebinding import rebind_artifact


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
async def test_rebinding_preserves_history_and_creates_dependency_edges(session_factory):
    async with session_factory() as session:
        user = User(email="rebind@example.test", name="Test", password_hash="x")
        session.add(user)
        await session.flush()
        project = Project(
            organization_id="org",
            name="Test project",
            created_by=user.id,
        )
        session.add(project)
        await session.flush()
        version = ProjectVersion(
            organization_id="org",
            project_id=project.id,
            version=1,
            created_by=user.id,
            status="COMMITTED",
        )
        session.add(version)
        await session.flush()
        world = WorldModelRevision(
            organization_id="org",
            project_id=project.id,
            project_version_id=version.id,
            revision=1,
            model_json={"schema": "test"},
            model_hash="w" * 64,
            created_by=user.id,
        )
        session.add(world)
        await session.flush()
        previous = ArtifactVersion(
            organization_id="org",
            project_id=project.id,
            project_version_id=version.id,
            world_model_revision_id=world.id,
            artifact_type="geometry",
            version=1,
            status="stale",
            provenance_json={"source_revision_hash": "old"},
            output_hash="o" * 64,
            payload_json={"old": True},
            created_by=user.id,
        )
        dependency = ArtifactVersion(
            organization_id="org",
            project_id=project.id,
            project_version_id=version.id,
            world_model_revision_id=world.id,
            artifact_type="design_alternative",
            version=1,
            status="current",
            output_hash="d" * 64,
            payload_json={"dependency": True},
            created_by=user.id,
        )
        session.add_all([previous, dependency])
        await session.flush()

        successor = await rebind_artifact(
            session,
            project=project,
            version=version,
            world=world,
            previous_artifact_id=previous.id,
            actor=user.id,
            payload={"new": True},
            source_revision_hash="new" * 16,
            dependencies=[dependency],
            engine_version="test-v1",
        )
        await session.commit()

        assert successor.id != previous.id
        assert successor.version == 2
        assert successor.status == "current"
        assert previous.status == "stale"
        assert successor.provenance_json["supersedes_artifact_version_id"] == previous.id
        edges = list(
            (
                await session.scalars(
                    select(ArtifactDependency).where(ArtifactDependency.artifact_version_id == successor.id)
                )
            ).all()
        )
        assert len(edges) == 1
        assert edges[0].depends_on_artifact_version_id == dependency.id
