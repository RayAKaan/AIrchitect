from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import ArtifactVersion
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
async def test_regeneration_service_commits_output_and_current_state() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(ArtifactVersion.__table__.create)
        await connection.run_sync(RegenerationStateRecord.__table__.create)
        await connection.run_sync(RegenerationJobRecord.__table__.create)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        artifact = ArtifactVersion(
            organization_id="org",
            project_id="project",
            project_version_id="version",
            artifact_type="geometry",
            version=1,
            status="stale",
            payload_json={"regeneration_request": {}},
            created_by="user",
        )
        session.add(artifact)
        await session.flush()
        state = RegenerationStateRecord(
            organization_id="org",
            project_id="project",
            project_version_id="version",
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
            project_id="project",
            project_version_id="version",
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

        assert output.output_hash == "output-hash"
        assert artifact.status == "current"
        assert artifact.version == 2
        assert artifact.output_hash == "output-hash"
        assert state.status == "CURRENT"
        assert state.output_revision_hash == "rev-2"
        assert job.status == "SUCCEEDED"
        assert job.locked_by is None

    await engine.dispose()
