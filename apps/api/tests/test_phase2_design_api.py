import uuid
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.db.models import Base, Membership
from app.db.session import get_session
from app.main import app

@pytest.fixture
async def api():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,expire_on_commit=False)
    app.state.test_session_factory = factory
    async def override():
        async with factory() as session:yield session
    app.dependency_overrides[get_session]=override
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:yield client
    app.dependency_overrides.clear()
    if hasattr(app.state, "test_session_factory"):
        delattr(app.state, "test_session_factory")
    await engine.dispose()

async def setup_committed(api,suffix="a"):
    email=f"p2-{suffix}-{uuid.uuid4().hex}@example.com"
    auth=await api.post("/api/v1/auth/register",json={"email":email,"name":"Designer","password":"phase-two-secure-password","organization_name":f"Org {suffix}"})
    h={"Authorization":"Bearer "+auth.json()["access_token"]};org=(await api.get("/api/v1/organizations",headers=h)).json()[0]
    project=(await api.post("/api/v1/projects",headers=h,json={"organization_id":org["id"],"name":"Retail Design","description":"P2","building_type":"commercial_retail","location":"Riyadh"})).json()
    version=(await api.get(f"/api/v1/projects/{project['id']}/versions",headers=h)).json()["versions"][0]
    brief=await api.post(f"/api/v1/projects/{project['id']}/versions/{version['id']}/brief",headers=h,json={
        "text":"Six-floor commercial retail building in Riyadh with 8,000 m2 GFA on a 2,000 m2 site and 40 parking spaces in basement parking.","expected_revision":1})
    assert brief.status_code==201,brief.text;rev=brief.json()["version_revision"]
    commit=await api.post(f"/api/v1/projects/{project['id']}/versions/{version['id']}/world-model",headers=h,json={"expected_revision":rev,"commit":True})
    assert commit.status_code==200,commit.text
    return h,org,project,commit.json()["version"]

async def generate_cad(api,cad,headers,project,version,alternative):
    cad.worker_with("ok")
    response=await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives/{alternative['id']}/cad",
        headers=headers,
        json={"requested_outputs":["glb"]},
    )
    assert response.status_code==201,response.text
    assert response.json()["geometry_artifact_id"]


async def test_design_api_generation_geometry_comparison_selection_and_tenant_isolation(api,cad):
    h,_,project,version=await setup_committed(api)
    generated=await api.post(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/generate",headers=h)
    assert generated.status_code==201,generated.text
    assert generated.json()["status"]=="COMPLETED" and len(generated.json()["alternative_ids"])==3
    assert generated.json()["idempotent"] is False
    repeated=await api.post(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/generate",headers=h)
    assert repeated.json()["generation_id"]==generated.json()["generation_id"] and repeated.json()["idempotent"] is True
    listing=(await api.get(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives",headers=h)).json()
    assert len(listing["alternatives"])==3
    alt=listing["alternatives"][0]
    await generate_cad(api,cad,h,project,version,alt)
    geometry=await api.get(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives/{alt['id']}/geometry",headers=h)
    assert geometry.status_code==200 and geometry.json()["geometry_hash"] and "geometry_ir" not in geometry.json()
    comparison=(await api.get(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/comparison",headers=h)).json()
    assert len(comparison["alternatives"])==3 and "No weighted overall score" in comparison["notice"]
    selected=await api.post(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives/{alt['id']}/select",headers=h,json={"reason":"Preferred open-site trade-off"})
    assert selected.status_code==200 and selected.json()["status"]=="SELECTED"
    other_h,_,_,_=await setup_committed(api,"b")
    denied=await api.get(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives",headers=other_h)
    assert denied.status_code==404 and denied.json()["error"]["code"]=="PROJECT_NOT_FOUND"

async def test_v2_has_no_v1_geometry_then_generates_new_hashes(api,cad):
    h,_,project,v1=await setup_committed(api)
    await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/design/generate",headers=h)
    v1_alts=(await api.get(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/design/alternatives",headers=h)).json()["alternatives"]
    for alternative in v1_alts:
        await generate_cad(api,cad,h,project,v1,alternative)
    v1_alts=(await api.get(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/design/alternatives",headers=h)).json()["alternatives"]
    v1_hashes={a["geometry_hash"] for a in v1_alts}
    created=await api.post(f"/api/v1/projects/{project['id']}/versions",headers={**h,"Idempotency-Key":"p2-floor-change"},json={
        "expected_current_version_id":v1["id"],"expected_revision":v1["revision_number"],"change_summary":"6 to 8 floors","changes":{"floor_count":8}})
    assert created.status_code==201,created.text;v2=created.json()["version"]
    empty=(await api.get(f"/api/v1/projects/{project['id']}/versions/{v2['id']}/design/alternatives",headers=h)).json()
    assert empty["alternatives"]==[]
    committed=await api.post(f"/api/v1/projects/{project['id']}/versions/{v2['id']}/world-model",headers=h,json={"expected_revision":v2["revision_number"],"commit":True})
    assert committed.status_code==200,committed.text
    generated=await api.post(f"/api/v1/projects/{project['id']}/versions/{v2['id']}/design/generate",headers=h)
    assert generated.status_code==201,generated.text
    v2_alts=(await api.get(f"/api/v1/projects/{project['id']}/versions/{v2['id']}/design/alternatives",headers=h)).json()["alternatives"]
    for alternative in v2_alts:
        await generate_cad(api,cad,h,project,v2,alternative)
    v2_alts=(await api.get(f"/api/v1/projects/{project['id']}/versions/{v2['id']}/design/alternatives",headers=h)).json()["alternatives"]
    assert len(v2_alts)==3 and v1_hashes.isdisjoint({a["geometry_hash"] for a in v2_alts})
    v1_again=(await api.get(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/design/alternatives",headers=h)).json()["alternatives"]
    assert {a["geometry_hash"] for a in v1_again}==v1_hashes
    assert all(a["status"] in {"VALID","SELECTED"} for a in v1_again)



async def test_design_direction_approval_requires_owner_and_is_idempotent(api):
    headers, org, project, version = await setup_committed(api, "approval")
    generated = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/generate",
        headers=headers,
    )
    assert generated.status_code == 201, generated.text
    alternatives = (await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives",
        headers=headers,
    )).json()["alternatives"]
    alternative = alternatives[0]

    selected = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives/{alternative['id']}/select",
        headers=headers,
        json={"reason": "Preferred balance of massing and open site."},
    )
    assert selected.status_code == 200, selected.text

    async with app.state.test_session_factory() as session:
        membership = await session.scalar(
            select(Membership).where(Membership.organization_id == org["id"])
        )
        membership.role = "member"
        await session.commit()

    denied = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives/{alternative['id']}/approve",
        headers=headers,
        json={"reason": "Approve this direction for further development."},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "APPROVAL_ROLE_REQUIRED"

    async with app.state.test_session_factory() as session:
        membership = await session.scalar(
            select(Membership).where(Membership.organization_id == org["id"])
        )
        membership.role = "owner"
        await session.commit()

    approved = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives/{alternative['id']}/approve",
        headers=headers,
        json={"reason": "Approve this direction for further development."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED_FOR_DEVELOPMENT"
    assert approved.json()["idempotent"] is False

    repeated = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives/{alternative['id']}/approve",
        headers=headers,
        json={"reason": "Approve this direction for further development."},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["idempotent"] is True
    assert repeated.json()["review_id"] == approved.json()["review_id"]

    comparison = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/comparison",
        headers=headers,
    )
    assert comparison.status_code == 200, comparison.text
    approved_alternative = next(
        item for item in comparison.json()["alternatives"] if item["id"] == alternative["id"]
    )
    assert approved_alternative["evaluation"]["constraint_summary"]["pass"] >= 0
    assert approved_alternative["provenance"]["design_direction_approval"]["status"] == "APPROVED_FOR_DEVELOPMENT"



async def test_s2_concept_endpoint_is_registered_and_requires_program_artifact(api):
    headers, _, project, version = await setup_committed(api, "s2-prerequisites")
    response = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/concepts/generate",
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROGRAM_REQUIRED"


async def test_s2_pipeline_generates_alternatives_from_current_program_and_envelope(api):
    email = f"s2-e2e-{uuid.uuid4().hex}@example.com"
    auth = await api.post("/api/v1/auth/register", json={
        "email": email,
        "name": "S2 Designer",
        "password": "phase-two-secure-password",
        "organization_name": "S2 E2E",
    })
    assert auth.status_code == 201, auth.text
    headers = {"Authorization": "Bearer " + auth.json()["access_token"]}
    organization = (await api.get("/api/v1/organizations", headers=headers)).json()[0]
    project = (await api.post("/api/v1/projects", headers=headers, json={
        "organization_id": organization["id"],
        "name": "S2 Retail Concept",
        "description": "End-to-end Phase 2 acceptance",
        "building_type": "commercial_retail",
        "location": "Riyadh",
    })).json()
    version = (await api.get(
        f"/api/v1/projects/{project['id']}/versions",
        headers=headers,
    )).json()["versions"][0]

    brief = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/brief",
        headers=headers,
        json={
            "text": "Six-floor commercial retail building in Riyadh with 8,000 m2 gross floor area on a 2,000 m2 site and 40 parking spaces in basement parking.",
            "expected_revision": 1,
        },
    )
    assert brief.status_code == 201, brief.text
    revision = brief.json()["version_revision"]

    extracted = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/requirements/extract",
        headers=headers,
    )
    assert extracted.status_code == 200, extracted.text
    assert extracted.json()["requirements"]
    for requirement in extracted.json()["requirements"]:
        confirmed = await api.post(
            f"/api/v1/projects/{project['id']}/versions/{version['id']}/requirements/{requirement['id']}/confirm",
            headers=headers,
            json={"decision": "CONFIRMED", "expected_revision": revision},
        )
        assert confirmed.status_code == 200, confirmed.text
        revision = confirmed.json()["version_revision"]

    longitude = 46.6753
    latitude = 24.7136
    delta_longitude = 50 / (111320 * 0.908)
    delta_latitude = 40 / 111320
    boundary = {
        "type": "Polygon",
        "coordinates": [[
            [longitude, latitude],
            [longitude + delta_longitude, latitude],
            [longitude + delta_longitude, latitude + delta_latitude],
            [longitude, latitude + delta_latitude],
            [longitude, latitude],
        ]],
    }
    site = await api.post(
        f"/api/v1/projects/{project['id']}/sites",
        headers=headers,
        json={
            "command_id": str(uuid.uuid4()),
            "idempotency_key": str(uuid.uuid4()),
            "boundary": boundary,
            "name": "S2 Test Site",
            "mode": "commit",
            "reason": "Create the canonical rectangular test site.",
        },
    )
    assert site.status_code == 201, site.text
    assert 1800 <= site.json()["area_m2"] <= 2200

    committed = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/world-model",
        headers=headers,
        json={"expected_revision": revision, "commit": True},
    )
    assert committed.status_code == 200, committed.text

    program = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/program/generate",
        headers=headers,
    )
    assert program.status_code == 200, program.text
    assert program.json()["program"]["target_gfa_m2"] == 8000
    assert program.json()["program"]["area_reconciliation"]["reconciled"] is True

    envelope = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/envelope/generate",
        headers=headers,
        json={
            "setback_m": {"value": 2, "unit": "m", "source": "USER_DESIGN_PARAMETER", "status": "DESIGN_PARAMETER"},
            "max_coverage": {"value": 0.8, "unit": "ratio", "source": "USER_DESIGN_PARAMETER", "status": "DESIGN_PARAMETER"},
            "far": {"value": 5.0, "unit": "ratio", "source": "USER_DESIGN_PARAMETER", "status": "DESIGN_PARAMETER"},
            "max_height_m": {"value": 30, "unit": "m", "source": "USER_DESIGN_PARAMETER", "status": "DESIGN_PARAMETER"},
        },
    )
    assert envelope.status_code == 200, envelope.text
    assert envelope.json()["envelope"]["max_gfa_m2"] > 8000
    assert envelope.json()["envelope"]["max_footprint_m2"] < envelope.json()["envelope"]["max_gfa_m2"]

    generated = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}/concepts/generate",
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["valid_alternative_count"] >= 2
    assert generated.json()["program_hash"] == program.json()["program_hash"]
    assert generated.json()["envelope_hash"] == envelope.json()["envelope_hash"]

    current = [
        alternative for alternative in generated.json()["alternatives"]
        if alternative["status"] == "VALID"
    ]
    assert len(current) >= 2
    for alternative in current:
        assert alternative["metrics"]["program_target_gfa_m2"] == 8000
        assert alternative["parameters"]["program_space_schedule"]
        assert alternative["parameters"]["program_adjacencies"]
        assert alternative["provenance"]["input_lineage"] == {
            "program": program.json()["program_hash"],
            "envelope": envelope.json()["envelope_hash"],
        }
        assert all(
            check["status"] != "FAIL"
            for check in alternative["constraint_results"]
        )
