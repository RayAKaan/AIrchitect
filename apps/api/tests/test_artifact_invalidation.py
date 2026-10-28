import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import ArtifactVersion
from app.db.regeneration_models import RegenerationStateRecord
from app.domains.commands.artifact_invalidation import ArtifactInvalidationService


@pytest.mark.asyncio
async def test_invalidation_marks_current_artifact_stale_and_persists_state() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(ArtifactVersion.__table__.create)
        await connection.run_sync(RegenerationStateRecord.__table__.create)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        artifact = ArtifactVersion(
            organization_id="org",
            project_id="project",
            project_version_id="version",
            artifact_type="geometry",
            version=1,
            status="current",
            created_by="user",
        )
        session.add(artifact)
        await session.flush()

        invalidated = await ArtifactInvalidationService().invalidate_groups(
            session,
            organization_id="org",
            project_id="project",
            project_version_id="version",
            source_revision_hash="rev-2",
            groups=("parametric_geometry_intents",),
        )
        await session.commit()

        assert invalidated == (artifact.id,)
        assert artifact.status == "stale"
        state = await session.scalar(
            select(RegenerationStateRecord).where(
                RegenerationStateRecord.artifact_version_id == artifact.id
            )
        )
        assert state is not None
        assert state.status == "INVALIDATED"
        assert state.source_revision_hash == "rev-2"

    await engine.dispose()


def test_unknown_impact_group_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown regeneration impact groups"):
        ArtifactInvalidationService._resolve_artifact_types(("not-real",))


@pytest.mark.asyncio
async def test_quantity_and_structural_impacts_match_registered_artifact_types() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(ArtifactVersion.__table__.create)
        await connection.run_sync(RegenerationStateRecord.__table__.create)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        quantity = ArtifactVersion(
            organization_id="org", project_id="project", project_version_id="version",
            artifact_type="quantity", version=1, status="current", created_by="user",
        )
        structural = ArtifactVersion(
            organization_id="org", project_id="project", project_version_id="version",
            artifact_type="structural", version=1, status="current", created_by="user",
        )
        session.add_all([quantity, structural])
        await session.flush()

        invalidated = await ArtifactInvalidationService().invalidate_groups(
            session,
            organization_id="org",
            project_id="project",
            project_version_id="version",
            source_revision_hash="rev-2",
            groups=("quantities", "structural_review"),
        )
        await session.commit()

        assert set(invalidated) == {quantity.id, structural.id}
        assert quantity.status == "stale"
        assert structural.status == "stale"

    await engine.dispose()
