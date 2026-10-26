from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import ArtifactDependency, ArtifactVersion, Base
from app.domains.lifecycle.artifact_provenance import build_provenance
from app.domains.lifecycle.release_gate import evaluate_release


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
async def test_release_gate_blocks_missing_required_artifacts(session_factory):
    async with session_factory() as session:
        result = await evaluate_release(session, project_version_id="version", required_types=("geometry",))
        assert result.ready is False
        assert result.blockers[0].code == "MISSING_CURRENT_ARTIFACT"
        assert result.blockers[0].artifact_type == "geometry"


@pytest.mark.asyncio
async def test_release_gate_accepts_current_provenanced_artifact(session_factory):
    async with session_factory() as session:
        dependency = ArtifactVersion(
            organization_id="org",
            project_id="project",
            project_version_id="version",
            artifact_type="design_alternative",
            version=1,
            status="current",
            output_hash="d" * 64,
            payload_json={},
            provenance_json={},
            created_by="user",
        )
        session.add(dependency)
        await session.flush()
        artifact = ArtifactVersion(
            organization_id="org",
            project_id="project",
            project_version_id="version",
            artifact_type="geometry",
            version=1,
            status="current",
            output_hash="a" * 64,
            payload_json={},
            provenance_json=build_provenance(
                source_revision_hash="s" * 64,
                dependencies=[dependency],
                engine_version="geometry-v1",
                config_version="config-v1",
            ),
            created_by="user",
        )
        session.add(artifact)
        await session.flush()
        session.add(
            ArtifactDependency(
                artifact_version_id=artifact.id,
                depends_on_artifact_version_id=dependency.id,
            )
        )
        await session.commit()
        result = await evaluate_release(session, project_version_id="version", required_types=("geometry",))
        assert result.ready is True
        assert result.blockers == ()
