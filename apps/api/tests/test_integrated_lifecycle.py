import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    ArtifactDependency, ArtifactVersion, Base, CostEstimate, DeliverableRecord, DesignAlternative,
    EvidenceRecord, GeometryArtifact, Organization, Project, ProjectVersion, QuantityArtifact,
    RateSchedule, RegulatoryEvaluation, StructuralArtifact, User, ValidationRun, WorkflowTaskRecord,
    WorldModelRevision,
)
from app.domains.lifecycle.service import canonical_hash, model_from_brief, run_pipeline, stale_prior_version


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


async def seed(session):
    user = User(email="engineer@example.com", name="Engineer", password_hash="x")
    session.add(user); await session.flush()
    org = Organization(name="Test organization", created_by=user.id)
    session.add(org); await session.flush()
    project = Project(organization_id=org.id, name="Riyadh retail feasibility", created_by=user.id)
    session.add(project); await session.flush()
    version = ProjectVersion(organization_id=org.id, project_id=project.id, version=1, created_by=user.id)
    session.add(version); await session.flush()
    model, unknowns = model_from_brief("Commercial retail on a site 50m x 40m, 4 floors, floor-to-floor 4.2 m, target 5000 m2")
    assert not unknowns
    world = WorldModelRevision(organization_id=org.id, project_id=project.id, project_version_id=version.id,
        revision=1, model_json=model, model_hash=canonical_hash(model), created_by=user.id)
    schedule = RateSchedule(organization_id=org.id, name="Demo", version="demo-v1", geography="Saudi Arabia demo",
        source="Seeded demo assumption — not market data", source_date="2026-09-25", is_demo=True,
        rates_json=[{"category":"gross_floor_area","unit":"m2","low":1000,"base":1500,"high":2000}], created_by=user.id)
    session.add_all([world, schedule]); await session.commit()
    return user, org, project, version, world, schedule


async def test_full_canonical_pipeline_persists_connected_artifact_graph(session):
    user, _, project, version, _, schedule = await seed(session)
    workflow = await run_pipeline(session, project, version, user.id, "full-run-0001", schedule)
    assert workflow.state == "succeeded"
    tasks = list((await session.scalars(select(WorkflowTaskRecord).where(WorkflowTaskRecord.workflow_id == workflow.id))).all())
    assert len(tasks) == 12 and all(task.state == "succeeded" for task in tasks)
    assert await session.scalar(select(func.count(DesignAlternative.id))) == 3
    assert await session.scalar(select(func.count(GeometryArtifact.id))) == 3
    assert await session.scalar(select(func.count(QuantityArtifact.id))) == 3
    assert await session.scalar(select(func.count(CostEstimate.id))) == 3
    assert await session.scalar(select(func.count(StructuralArtifact.id))) == 3
    assert await session.scalar(select(func.count(RegulatoryEvaluation.id))) == 3
    assert await session.scalar(select(func.count(ValidationRun.id))) == 1
    assert await session.scalar(select(func.count(EvidenceRecord.id))) > 0
    assert await session.scalar(select(func.count(ArtifactDependency.id))) > 20
    deliverable = await session.scalar(select(DeliverableRecord))
    assert deliverable.status == "awaiting_review"
    assert deliverable.payload_json["project_version_id"] == version.id
    regulatory = await session.scalar(select(RegulatoryEvaluation))
    assert regulatory.status == "unknown"
    structure = await session.scalar(select(StructuralArtifact))
    assert structure.status == "concept_only"


async def test_idempotency_and_change_stale_propagation(session):
    user, _, project, version, _, schedule = await seed(session)
    first = await run_pipeline(session, project, version, user.id, "full-run-0002", schedule)
    second = await run_pipeline(session, project, version, user.id, "full-run-0002", schedule)
    assert first.id == second.id
    stale_ids = await stale_prior_version(session, version)
    await session.commit()
    artifacts = list((await session.scalars(select(ArtifactVersion).where(ArtifactVersion.project_version_id == version.id))).all())
    assert stale_ids and all(a.status == "stale" for a in artifacts)
    deliverable = await session.scalar(select(DeliverableRecord))
    assert deliverable.status == "stale"


async def test_geometry_hashes_are_deterministic_through_pipeline(session):
    user, _, project, version, _, schedule = await seed(session)
    await run_pipeline(session, project, version, user.id, "full-run-0003", schedule)
    hashes = [g.geometry_hash for g in (await session.scalars(select(GeometryArtifact).order_by(GeometryArtifact.alternative_id))).all()]
    assert len(hashes) == 3 and all(len(value) == 64 for value in hashes) and len(set(hashes)) == 3
