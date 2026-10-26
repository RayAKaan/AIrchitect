import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import ArtifactDependency, ArtifactVersion, Base
from app.domains.lifecycle.dependency_integrity import validate_dependency_integrity


@pytest.mark.asyncio
async def test_dependency_cycle_is_rejected():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        a = ArtifactVersion(organization_id="o", project_id="p", project_version_id="v", artifact_type="a", version=1, created_by="u")
        b = ArtifactVersion(organization_id="o", project_id="p", project_version_id="v", artifact_type="b", version=1, created_by="u")
        session.add_all([a, b]); await session.flush()
        session.add_all([ArtifactDependency(artifact_version_id=a.id, depends_on_artifact_version_id=b.id), ArtifactDependency(artifact_version_id=b.id, depends_on_artifact_version_id=a.id)])
        await session.commit()
        errors = await validate_dependency_integrity(session, project_version_id="v")
        assert any(error.code == "DEPENDENCY_CYCLE" for error in errors)
    await engine.dispose()
