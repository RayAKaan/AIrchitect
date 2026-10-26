from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import ArtifactDependency, ArtifactVersion, Base
from app.domains.lifecycle.release_manifest import build_release_manifest


@pytest.mark.asyncio
async def test_release_manifest_is_deterministic_and_orders_dependencies() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        first = ArtifactVersion(
            organization_id="org",
            project_id="project",
            project_version_id="version",
            artifact_type="cost",
            version=1,
            status="current",
            output_hash="b" * 64,
            provenance_json={"source": "quantity"},
            payload_json={},
            created_by="user",
        )
        second = ArtifactVersion(
            organization_id="org",
            project_id="project",
            project_version_id="version",
            artifact_type="quantity",
            version=1,
            status="current",
            output_hash="a" * 64,
            provenance_json={},
            payload_json={},
            created_by="user",
        )
        session.add_all([first, second])
        await session.flush()
        session.add(ArtifactDependency(
            artifact_version_id=first.id,
            depends_on_artifact_version_id=second.id,
        ))
        await session.commit()

        manifest = await build_release_manifest(session, project_version_id="version")
        again = await build_release_manifest(session, project_version_id="version")

        assert manifest.manifest_hash == again.manifest_hash
        assert [item.artifact_type for item in manifest.artifacts] == ["cost", "quantity"]
        assert manifest.artifacts[0].dependency_ids == (second.id,)
        assert json.loads(json.dumps(manifest.as_dict(), sort_keys=True))["manifest_hash"] == manifest.manifest_hash
    await engine.dispose()
