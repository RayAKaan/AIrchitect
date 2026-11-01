from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    ArtifactDependency,
    ArtifactVersion,
    Base,
    Project,
    ProjectVersion,
    WorldModelRevision,
)
from app.db.regeneration_job_models import RegenerationJobRecord
from app.db.regeneration_models import RegenerationStateRecord
from app.domains.commands.regeneration_executor import RegenerationOutput
from app.domains.commands.regeneration_service import RegenerationService


class FakeHandlers:
    def execute(self, request):
        return RegenerationOutput(
            artifact_type=request.artifact_type,
            source_revision_hash=request.source_revision_hash,
            payload={"regenerated": True},
            output_hash="output-hash",
            engine_version="test-engine",
        )


@pytest.mark.asyncio
async def test_regeneration_publishes_immutable_successor_and_rebinds_dependencies() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        project = Project(
            id="project",
            organization_id="org",
            name="Regeneration test",
            created_by="user",
        )
        version = ProjectVersion(
            id="version",
            organization_id="org",
            project_id=project.id,
            version=1,
            created_by="user",
        )
        world = WorldModelRevision(
            id="world",
            organization_id="org",
            project_id=project.id,
            project_version_id=version.id,
            revision=2,
            model_json={"schema": "test"},
            model_hash="rev-2",
            created_by="user",
        )
        session.add_all([project, version, world])
        await session.flush()

        artifact = ArtifactVersion(
            id="geometry-v1",
            organization_id="org",
            project_id=project.id,
            project_version_id=version.id,
            world_model_revision_id=world.id,
            artifact_type="geometry",
            version=1,
            status="stale",
            payload_json={"regeneration_request": {}},
            output_hash="old-output",
            created_by="user",
        )
        dependency_v1 = ArtifactVersion(
            id="design-v1",
            organization_id="org",
            project_id=project.id,
            project_version_id=version.id,
            world_model_revision_id=world.id,
            alternative_id="alternative-1",
            artifact_type="design_alternative",
            version=1,
            status="stale",
            output_hash="old-design",
            payload_json={"version": 1},
            created_by="user",
        )
        dependency_v2 = ArtifactVersion(
            id="design-v2",
            organization_id="org",
            project_id=project.id,
            project_version_id=version.id,
            world_model_revision_id=world.id,
            alternative_id="alternative-1",
            artifact_type="design_alternative",
            version=2,
            status="current",
            output_hash="current-design",
            payload_json={"version": 2},
            created_by="user",
        )
        session.add_all([artifact, dependency_v1, dependency_v2])
        await session.flush()
        session.add(
            ArtifactDependency(
                artifact_version_id=artifact.id,
                depends_on_artifact_version_id=dependency_v1.id,
            )
        )
        await session.flush()

        state = RegenerationStateRecord(
            organization_id="org",
            project_id=project.id,
            project_version_id=version.id,
            artifact_version_id=artifact.id,
            source_revision_hash="rev-2",
            status="RUNNING",
            generation_key="geometry:rev-2",
        )
        session.add(state)
        await session.flush()
        job = RegenerationJobRecord(
            regeneration_state_id=state.id,
            organization_id="org",
            project_id=project.id,
            project_version_id=version.id,
            artifact_version_id=artifact.id,
            source_revision_hash="rev-2",
            status="RUNNING",
            attempt_count=1,
            locked_by="worker-1",
            locked_at=datetime.now(timezone.utc),
        )
        session.add(job)
        await session.flush()

        output = await RegenerationService(FakeHandlers()).execute_job(
            session, job.id, worker_id="worker-1", attempt_count=1
        )
        await session.commit()

        artifacts = list(
            (
                await session.scalars(
                    select(ArtifactVersion)
                    .where(
                        ArtifactVersion.project_version_id == version.id,
                        ArtifactVersion.artifact_type == "geometry",
                    )
                    .order_by(ArtifactVersion.version)
                )
            ).all()
        )
        assert output.output_hash == "output-hash"
        assert len(artifacts) == 2
        assert artifacts[0].id == artifact.id
        assert artifacts[0].version == 1
        assert artifacts[0].status == "stale"
        assert artifacts[0].payload_json == {"regeneration_request": {}}
        successor = artifacts[1]
        assert successor.version == 2
        assert successor.status == "current"
        assert successor.world_model_revision_id == world.id
        assert successor.output_hash == "output-hash"
        assert successor.provenance_json["supersedes_artifact_version_id"] == artifact.id
        assert successor.input_references_json == [dependency_v2.id]

        edges = list(
            (
                await session.scalars(
                    select(ArtifactDependency).where(
                        ArtifactDependency.artifact_version_id == successor.id
                    )
                )
            ).all()
        )
        assert len(edges) == 1
        assert edges[0].depends_on_artifact_version_id == dependency_v2.id

        old_state = await session.get(RegenerationStateRecord, state.id)
        new_state = await session.scalar(
            select(RegenerationStateRecord).where(
                RegenerationStateRecord.artifact_version_id == successor.id
            )
        )
        assert old_state.status == "SUCCEEDED"
        assert new_state is not None
        assert new_state.status == "CURRENT"
        assert new_state.output_revision_hash == "rev-2"
        assert job.status == "SUCCEEDED"
        assert job.locked_by is None

    await engine.dispose()
