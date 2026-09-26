import uuid
import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.db.models import Base
from app.db.session import get_session
from app.main import app

@pytest.fixture
async def api():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,expire_on_commit=False)
    async def override():
        async with factory() as session:yield session
    app.dependency_overrides[get_session]=override
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:yield client
    app.dependency_overrides.clear();await engine.dispose()

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

async def test_design_api_generation_geometry_comparison_selection_and_tenant_isolation(api):
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
    geometry=await api.get(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives/{alt['id']}/geometry",headers=h)
    assert geometry.status_code==200 and geometry.json()["geometry_ir"]["floor_plates"]
    comparison=(await api.get(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/comparison",headers=h)).json()
    assert len(comparison["alternatives"])==3 and "No single optimal" in comparison["notice"]
    selected=await api.post(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives/{alt['id']}/select",headers=h,json={"reason":"Preferred open-site trade-off"})
    assert selected.status_code==200 and selected.json()["status"]=="SELECTED"
    other_h,_,_,_=await setup_committed(api,"b")
    denied=await api.get(f"/api/v1/projects/{project['id']}/versions/{version['id']}/design/alternatives",headers=other_h)
    assert denied.status_code==404 and denied.json()["error"]["code"]=="PROJECT_NOT_FOUND"

async def test_v2_has_no_v1_geometry_then_generates_new_hashes(api):
    h,_,project,v1=await setup_committed(api)
    await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/design/generate",headers=h)
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
    assert len(v2_alts)==3 and v1_hashes.isdisjoint({a["geometry_hash"] for a in v2_alts})
    v1_again=(await api.get(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/design/alternatives",headers=h)).json()["alternatives"]
    assert {a["geometry_hash"] for a in v1_again}==v1_hashes
    assert all(a["status"] in {"VALID","SELECTED"} for a in v1_again)
