import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import ArtifactVersion, Base, Project, ProjectVersion, WorldModelRevision
from app.db.regeneration_job_models import RegenerationJobRecord
from app.db.regeneration_models import RegenerationStateRecord
from app.domains.commands.artifact_lifecycle import invalidate_and_enqueue
from app.domains.commands.regeneration_executor import RegenerationOutput
from app.domains.commands.regeneration_queue import RegenerationQueue
from app.domains.commands.regeneration_repository import RegenerationStateRepository
from app.domains.commands.regeneration_service import RegenerationService
from app.domains.commands.regeneration_worker import RegenerationWorker


class DeterministicHandlers:
    def execute(self, request):
        return RegenerationOutput(
            artifact_type=request.artifact_type,
            source_revision_hash=request.source_revision_hash,
            payload={"generated_from": request.source_revision_hash},
            output_hash="successor-output-hash",
            engine_version="acceptance-test-v1",
        )


@pytest.mark.asyncio
async def test_canonical_artifact_lifecycle_invalidates_queues_regenerates_and_preserves_history():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        project = Project(
            id="phase1-project",
            organization_id="phase1-org",
            name="Phase 1 lifecycle acceptance",
            created_by="phase1-user",
        )
        version = ProjectVersion(
            id="phase1-version",
            organization_id="phase1-org",
            project_id=project.id,
            version=1,
            created_by="phase1-user",
        )
        world = WorldModelRevision(
            id="phase1-world-rev-2",
            organization_id="phase1-org",
            project_id=project.id,
            project_version_id=version.id,
            revision=2,
            model_json={"schema": "acceptance"},
            model_hash="revision-2",
            created_by="phase1-user",
        )
        artifact = ArtifactVersion(
            id="phase1-geometry-v1",
            organization_id="phase1-org",
            project_id=project.id,
            project_version_id=version.id,
            world_model_revision_id=world.id,
            artifact_type="geometry",
            version=1,
            status="current",
            provenance_json={"source_revision_hash": "revision-1"},
            output_hash="original-output-hash",
            payload_json={"regeneration_request": {"test": True}},
            created_by="phase1-user",
        )
        session.add_all([project, version, world, artifact])
        await session.flush()

        states = RegenerationStateRepository()
        state = await states.create_current(
            session,
            organization_id=project.organization_id,
            project_id=project.id,
            project_version_id=version.id,
            artifact_version_id=artifact.id,
            source_revision_hash="revision-1",
            generation_key="geometry:revision-1",
        )
        await session.commit()

        queue = RegenerationQueue(states)
        invalidated = await invalidate_and_enqueue(
            session,
            project=project,
            version=version,
            source_revision_hash="revision-2",
            groups=["parametric_geometry_intents"],
            state_repository_factory=lambda: states,
            queue_factory=lambda repository: queue,
        )
        await session.commit()

        assert invalidated == (artifact.id,)
        assert artifact.status == "stale"
        job = await session.scalar(
            select(RegenerationJobRecord).where(
                RegenerationJobRecord.artifact_version_id == artifact.id
            )
        )
        assert job is not None
        assert job.status == "QUEUED"

        worker = RegenerationWorker(
            worker_id="phase1-worker",
            queue=queue,
            service=RegenerationService(DeterministicHandlers(), states),
        )
        result = await worker.run_once(session)

        assert result.status == "SUCCEEDED"
        assert result.job_id == job.id

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
        assert len(artifacts) == 2
        assert artifacts[0].id == artifact.id
        assert artifacts[0].version == 1
        assert artifacts[0].status == "stale"
        assert artifacts[0].payload_json == {"regeneration_request": {"test": True}}

        successor = artifacts[1]
        assert successor.version == 2
        assert successor.status == "current"
        assert successor.world_model_revision_id == world.id
        assert successor.payload_json == {"generated_from": "revision-2"}
        assert successor.output_hash == "successor-output-hash"
        assert successor.provenance_json["supersedes_artifact_version_id"] == artifact.id

        old_state = await session.get(RegenerationStateRecord, state.id)
        current_state = await session.scalar(
            select(RegenerationStateRecord).where(
                RegenerationStateRecord.artifact_version_id == successor.id
            )
        )
        refreshed_job = await session.get(RegenerationJobRecord, job.id)
        assert old_state is not None and old_state.status == "SUCCEEDED"
        assert current_state is not None and current_state.status == "CURRENT"
        assert current_state.output_revision_hash == "revision-2"
        assert refreshed_job is not None and refreshed_job.status == "SUCCEEDED"
        assert refreshed_job.locked_by is None

    await engine.dispose()
