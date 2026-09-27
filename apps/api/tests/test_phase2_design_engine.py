import copy
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    ArtifactDependency, ArtifactVersion, Base, CadJobRun, DesignAlternative, DesignConstraintRecord,
    DesignGenerationRun, GeometryArtifact, Membership, Organization, Project, ProjectVersion, User,
    WorldModelRevision, QuantityArtifact, StructuralArtifact, RegulatoryEvaluation, ValidationRun,
)
from app.domains.design.config import DEFAULT_CONFIG
from app.domains.design.constraints import DesignConstraintResolver
from app.domains.design.engine import ENGINE, DesignGenerationError
from app.domains.design.geometry_ir import GeometryValidator, MassingGeometryEngine
from app.domains.design.strategies import STRATEGIES
from app.domains.lifecycle.service import canonical_hash
from app.domains.engineering.service import calculate_all
from app.domains.cad.persistence import record_cad_success
from app.domains.cad.protocol import CadJobResult, CadJobRequest, SolidMeasurement, Footprint, MassingElement


def _make_fake_cad_result():
    """Create a mock CAD job result with standard measurements for testing."""
    from app.domains.cad.protocol import CadJobResult, SolidMeasurement
    measurements = [
        SolidMeasurement(
            id="mass-1",
            kind="building_mass",
            volume_m3=3000.0,
            surface_area_m2=1400.0,
            centroid=[5.0, 5.0, 15.0],
            bounding_box={"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 30.0]},
            solid_count=1,
            face_count=6,
            edge_count=12,
            vertex_count=8,
            is_valid=True,
            is_closed=True,
        )
    ]
    return CadJobResult(
        schema_version="1.0",
        job_id="test-job",
        status="ok",
        provider={
            "provider": "occt",
            "engine_name": "fake",
            "engine_version": "0",
            "occt_version": "7.9.3",
            "python_version": "3.12",
        },
        measurements=[
            SolidMeasurement(
                id="mass-1",
                kind="building_mass",
                volume_m3=3000.0,
                surface_area_m2=1400.0,
                centroid=[5.0, 5.0, 15.0],
                bounding_box={"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 30.0]},
                solid_count=1,
                face_count=6,
                edge_count=12,
                vertex_count=8,
                is_valid=True,
                is_closed=True,
            )
        ],
        combined_volume_m3=3000.0,
        combined_area_m2=1400.0,
        combined_bounding_box={"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 30.0]},
        artifacts=[],
        validation={"valid": True, "checks": [], "errors": [], "warnings": []},
        element_count=1,
        warnings=[],
    )


async def _create_cad_geometry(session, project, version, world, alt_id, user_id, design_hash="", alternative_id=None):
    """Create a CAD_BREP geometry artifact for testing."""
    from app.domains.cad.persistence import record_cad_success
    from app.domains.cad.protocol import CadJobRequest

    recorded = await record_cad_success(
        session=session,
        project=project,
        version=version,
        world=world,
        actor_id=user_id,
        provider="occt",
        request=CadJobRequest(
            elements=[MassingElement(
                id="mass-1",
                name="Test Mass",
                footprint=Footprint(points=[[0,0],[10,0],[10,10],[0,10]]),
                base_elevation_m=0.0,
                height_m=30.0,
                material_class="conceptual_mass",
            )],
            outputs=["glb"],
        ),
        result=_make_fake_cad_result(),
        stored={},
        alternative_id=alt_id,
        design_hash=design_hash or "",
        duration_ms=100,
    )
    return recorded


@pytest.fixture
async def session():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,expire_on_commit=False)
    async with factory() as value:yield value
    await engine.dispose()


def world_payload(project_id="p",version_id="v",floors=6,properties=None,confirmed=True):
    return {"schema_version":"1.0.0","project_id":project_id,"project_version_id":version_id,
        "site":{"location":{"city":"Riyadh","country":"Saudi Arabia"},"area":{"value":2000.0,"unit":"m2"},
            "width":None,"depth":None,"boundary":None,"orientation":None},
        "building":{"use":"commercial_retail","floor_count":floors,
            "floor_to_floor_height":{"value":4.0,"unit":"m"},"height":{"value":floors*4.0,"unit":"m"},
            "target_gfa":{"value":8000.0,"unit":"m2"},"coverage":None},
        "levels":[],"spaces":[],"parking":{"arrangement":"basement","spaces":{"value":40,"unit":"count"}},
        "structural_grid":{"system":None,"x_spacings_m":[],"y_spacings_m":[]},"properties":properties or {},
        "requirement_ids":["r1"],"assumption_ids":["a1"],
        "provenance":{"site_area":{"source_type":"USER_BRIEF","source_id":"r-site","confirmed":True},
            "floor_count":{"source_type":"USER_BRIEF","source_id":"r-floor","confirmed":confirmed},
            "target_gfa":{"source_type":"USER_BRIEF","source_id":"r-gfa","confirmed":True},
            "floor_to_floor_height":{"source_type":"SYSTEM_ASSUMPTION","source_id":"a-height","confirmed":True},
            "parking_spaces":{"source_type":"USER_BRIEF","source_id":"r-parking","confirmed":True}},
        "unknowns":["site.boundary","building.maximum_height"],"consistency_issues":[]}


async def seed(session,floors=6,properties=None):
    user=User(email=f"u{floors}@example.com",name="Designer",password_hash="x");session.add(user);await session.flush()
    org=Organization(name="Design Org",created_by=user.id);session.add(org);await session.flush()
    session.add(Membership(organization_id=org.id,user_id=user.id,role="owner"))
    project=Project(organization_id=org.id,name="Retail",created_by=user.id);session.add(project);await session.flush()
    version=ProjectVersion(organization_id=org.id,project_id=project.id,version=1,status="COMMITTED",revision_number=2,created_by=user.id)
    session.add(version);await session.flush();project.current_version_id=version.id
    payload=world_payload(project.id,version.id,floors,properties);world=WorldModelRevision(organization_id=org.id,
        project_id=project.id,project_version_id=version.id,revision=1,model_json=payload,model_hash=canonical_hash(payload),created_by=user.id)
    session.add(world);await session.commit();return user,org,project,version,world


def test_constraint_classes_unknowns_and_search_space():
    model=world_payload(confirmed=True)
    context=DesignConstraintResolver(DEFAULT_CONFIG).resolve(model,canonical_hash(model))
    classes={c.parameter:c.classification for c in context.constraints}
    assert classes["site_area"]=="HARD" and classes["floor_count"]=="HARD"
    assert classes["target_gfa"]=="PREFERRED" and classes["setback"]=="FLEXIBLE"
    assert classes["max_height"]=="UNKNOWN"
    assert context.search_space.site_boundary_source=="derived_rectangular_approximation"
    assert any(a["parameter"]=="site_boundary" for a in context.search_space.assumptions)


def test_strategies_are_deterministic_and_materially_different():
    model=world_payload();context=DesignConstraintResolver(DEFAULT_CONFIG).resolve(model,canonical_hash(model))
    outputs=[]
    for strategy in STRATEGIES:
        first=strategy.generate_candidates(context,DEFAULT_CONFIG,8000,6,4,40)
        second=strategy.generate_candidates(context,DEFAULT_CONFIG,8000,6,4,40)
        assert [x.model_dump() for x in first]==[x.model_dump() for x in second]
        outputs.append(next(c for c in first if c.valid))
    dimensions={(round(c.parameters["footprint_width_m"],3),round(c.parameters["footprint_depth_m"],3),c.metrics["gross_floor_area_m2"]) for c in outputs}
    assert len(dimensions)==3
    assert all(any(r["classification"]=="HARD" and r["status"]=="PASS" for r in c.constraint_results) for c in outputs)


def test_preferred_deviation_and_hard_failure_are_distinct():
    model=world_payload(properties={"max_coverage":.4});context=DesignConstraintResolver(DEFAULT_CONFIG).resolve(model,canonical_hash(model))
    candidates=STRATEGIES[0].generate_candidates(context,DEFAULT_CONFIG,8000,6,4,40)
    assert all(not c.valid for c in candidates)
    assert any(r["parameter"]=="max_coverage" and r["status"]=="FAIL" for r in candidates[0].constraint_results)
    assert any(r["parameter"]=="target_gfa" and r["status"] in {"PASS","DEVIATION"} for r in candidates[0].constraint_results)


async def test_generation_persists_three_alternatives_geometry_and_lineage(session):
    user,_,project,version,world=await seed(session)
    run=await ENGINE.generate(session,project,version,world,user)
    assert run.status=="COMPLETED" and len(run.generated_alternative_ids_json)==3
    alternatives=list((await session.scalars(select(DesignAlternative).order_by(DesignAlternative.strategy_id))).all())
    geometries=list((await session.scalars(select(GeometryArtifact).order_by(GeometryArtifact.geometry_hash))).all())
    assert {a.strategy_id for a in alternatives}=={"balanced","compact","low_rise"}
    assert len({a.design_hash for a in alternatives})==3 and len({g.geometry_hash for g in geometries})==3
    assert all(a.input_world_model_hash==world.model_hash and a.design_engine_version=="0.2.0" for a in alternatives)
    assert all(g.input_world_model_hash==world.model_hash and g.engine_name=="MassingGeometryEngine" for g in geometries)
    assert await session.scalar(select(func.count(DesignConstraintRecord.id)))>=7
    assert await session.scalar(select(func.count(ArtifactDependency.id)))==3
    assert all(len(g.payload_json["geometry_ir"]["floor_plates"])==6 for g in geometries)
    assert all(g.payload_json["validation"]["valid"] for g in geometries)


async def test_generation_is_idempotent(session):
    user,_,project,version,world=await seed(session)
    first=await ENGINE.generate(session,project,version,world,user)
    second=await ENGINE.generate(session,project,version,world,user)
    assert first.id==second.id
    assert await session.scalar(select(func.count(DesignGenerationRun.id)))==1
    assert await session.scalar(select(func.count(DesignAlternative.id)))==3


async def test_conflicting_constraints_persist_failed_run_without_artifacts(session):
    user,_,project,version,world=await seed(session,properties={"max_coverage":.4})
    with pytest.raises(DesignGenerationError) as caught:await ENGINE.generate(session,project,version,world,user)
    assert caught.value.code=="NO_VALID_CANDIDATE"
    run=await session.scalar(select(DesignGenerationRun));assert run.status=="FAILED"
    assert await session.scalar(select(func.count(DesignAlternative.id)))==0
    assert await session.scalar(select(func.count(GeometryArtifact.id)))==0


async def test_unexpected_failure_is_durable_and_rolls_back_partial_artifacts(session,monkeypatch):
    user,_,project,version,world=await seed(session)
    ids=(user.id,project.id,version.id,world.id)
    def explode(*args,**kwargs):raise RuntimeError("simulated geometry runtime failure")
    monkeypatch.setattr(ENGINE.geometry_engine,"generate",explode)
    with pytest.raises(DesignGenerationError) as caught:await ENGINE.generate(session,project,version,world,user)
    assert caught.value.code=="DESIGN_GENERATION_INTERNAL_ERROR"
    run=await session.scalar(select(DesignGenerationRun));assert run.status=="FAILED" and run.error_code=="DESIGN_GENERATION_INTERNAL_ERROR"
    assert await session.scalar(select(func.count(DesignAlternative.id)))==0
    assert await session.scalar(select(func.count(GeometryArtifact.id)))==0
    monkeypatch.undo()
    user_id,project_id,version_id,world_id=ids
    project=await session.get(Project,project_id);version=await session.get(ProjectVersion,version_id)
    world=await session.get(WorldModelRevision,world_id);user=await session.get(User,user_id)
    retried=await ENGINE.generate(session,project,version,world,user)
    assert retried.id==run.id and retried.status=="COMPLETED"
    assert await session.scalar(select(func.count(DesignAlternative.id)))==3


async def test_geometry_ir_metrics_and_hash_are_reproducible(session):
    user,_,project,version,world=await seed(session)
    await ENGINE.generate(session,project,version,world,user)
    alt=await session.scalar(select(DesignAlternative).where(DesignAlternative.strategy_id=="balanced"))
    geom=await session.scalar(select(GeometryArtifact).where(GeometryArtifact.alternative_id==alt.id))
    ir=geom.payload_json["geometry_ir"]
    assert ir["site"]["type"]=="site_boundary" and ir["masses"][0]["type"]=="building_mass"
    assert len(ir["floor_plates"])==alt.key_metrics_json["floor_count"]
    assert ir["parking"]["geometry_status"]=="NOT_GENERATED"
    assert geom.geometry_hash==canonical_hash({"geometry_ir":ir,"geometry_engine_version":geom.engine_version,"design_hash":alt.design_hash})


async def test_world_hash_change_marks_same_version_artifacts_stale(session):
    user,org,project,version,world=await seed(session)
    await ENGINE.generate(session,project,version,world,user)
    selected=await session.scalar(select(DesignAlternative).where(DesignAlternative.strategy_id=="balanced"))
    
    # Create CAD geometry for the alternative (required for authoritative engineering)
    recorded = await _create_cad_geometry(
        session, project, version, world, selected.id, user.id,
        design_hash=selected.design_hash or "", alternative_id=selected.id
    )
    selected_geom = await session.get(GeometryArtifact, recorded.geometry_artifact_id)
    assert selected_geom is not None
    assert selected_geom.source == "CAD_BREP"
    
    await calculate_all(session,project,version,world,selected,selected_geom,user,None)
    changed=copy.deepcopy(world.model_json);changed["building"]["target_gfa"]["value"]=7600
    newer=WorldModelRevision(organization_id=org.id,project_id=project.id,project_version_id=version.id,revision=2,
        model_json=changed,model_hash=canonical_hash(changed),created_by=user.id);session.add(newer);await session.commit()
    await ENGINE.generate(session,project,version,newer,user)
    old=list((await session.scalars(select(DesignAlternative).where(DesignAlternative.input_world_model_hash==world.model_hash))).all())
    new=list((await session.scalars(select(DesignAlternative).where(DesignAlternative.input_world_model_hash==newer.model_hash))).all())
    assert old and all(a.status=="STALE" for a in old)
    assert new and all(a.status=="VALID" for a in new)
    old_geoms=list((await session.scalars(select(GeometryArtifact).where(GeometryArtifact.input_world_model_hash==world.model_hash))).all())
    assert all(g.status=="STALE" for g in old_geoms)
    assert (await session.scalar(select(QuantityArtifact))).status=="STALE"
    assert (await session.scalar(select(StructuralArtifact))).status=="STALE"
    assert (await session.scalar(select(RegulatoryEvaluation))).status=="STALE"
    assert (await session.scalar(select(ValidationRun))).status=="STALE"
