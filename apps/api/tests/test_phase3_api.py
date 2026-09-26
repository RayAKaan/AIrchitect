import uuid
import httpx,pytest
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.db.models import (ArtifactDependency,Base,CostEstimate,QuantityArtifact,RateSchedule,RegulatoryEvaluation,
 StructuralArtifact,ValidationRun)
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
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:yield client,factory
 app.dependency_overrides.clear();await engine.dispose()
async def setup(api,suffix="a"):
 email=f"p3-{suffix}-{uuid.uuid4().hex}@example.com";auth=await api.post("/api/v1/auth/register",json={"email":email,"name":"Engineer","password":"phase-three-secure","organization_name":f"P3 {suffix}"});h={"Authorization":"Bearer "+auth.json()["access_token"]};org=(await api.get("/api/v1/organizations",headers=h)).json()[0]
 p=(await api.post("/api/v1/projects",headers=h,json={"organization_id":org["id"],"name":"Engineering Study","description":"P3","building_type":"commercial_retail","location":"Riyadh"})).json();v=(await api.get(f"/api/v1/projects/{p['id']}/versions",headers=h)).json()["versions"][0]
 b=await api.post(f"/api/v1/projects/{p['id']}/versions/{v['id']}/brief",headers=h,json={"text":"Six-floor commercial retail building in Riyadh with 8,000 m2 GFA on a 2,000 m2 site and 40 parking spaces in basement parking.","expected_revision":1});rev=b.json()["version_revision"]
 c=await api.post(f"/api/v1/projects/{p['id']}/versions/{v['id']}/world-model",headers=h,json={"expected_revision":rev,"commit":True});v=c.json()["version"]
 g=await api.post(f"/api/v1/projects/{p['id']}/versions/{v['id']}/design/generate",headers=h);aid=g.json()["alternative_ids"][0]
 return h,org,p,v,aid

async def test_phase3_calculation_cost_unavailable_then_sourced_cost_idempotency_and_lineage(api):
 client,factory=api;h,org,p,v,aid=await setup(client)
 base=f"/api/v1/projects/{p['id']}/versions/{v['id']}/design/alternatives/{aid}/engineering"
 first=await client.post(base+"/calculate",headers=h,json={});assert first.status_code==201,first.text;data=first.json()
 assert data["quantity"]["validation"]["valid"] and data["quantity"]["status"]=="CURRENT"
 assert data["cost"] is None and data["cost_error"]["code"]=="COST_UNAVAILABLE"
 assert data["structure"]["foundation_concept"]=="UNKNOWN" and "Not safety certification" in data["structure"]["disclaimer"]
 assert data["regulatory"]["overall_status"]=="UNKNOWN" and data["regulatory"]["summary"]["UNKNOWN"]==4
 assert data["validation"]["status"]=="CURRENT" and data["validation"]["human_review_required"]
 schedule=await client.post("/api/v1/engineering/rate-schedules",headers=h,json={"organization_id":org["id"],"name":"User conceptual allowance","version":"user-2026-1","jurisdiction":"Riyadh","currency":"SAR","source_reference":"User-uploaded feasibility budget dated 2026-09-01","effective_date":"2026-09-01","source_type":"USER_PROVIDED","entries":[{"item_code":"GFA_ALLOWANCE","category":"Other","description":"User conceptual GFA allowance","quantity_code":"GFA","unit":"m2","rate":1000,"low_rate":900,"high_rate":1150,"source_reference":"User-uploaded feasibility budget dated 2026-09-01","effective_date":"2026-09-01","confidence":"USER_DECLARED"}]});assert schedule.status_code==201,schedule.text;sid=schedule.json()["id"]
 costed=await client.post(base+"/calculate",headers=h,json={"rate_schedule_id":sid});assert costed.status_code==201,costed.text;out=costed.json()
 assert out["reused"]["quantity"] and out["reused"]["structure"] and out["reused"]["regulatory"]
 assert out["cost"]["currency"]=="SAR" and out["cost"]["total_cost"]>0 and out["cost"]["low_estimate"]<out["cost"]["high_estimate"]
 again=await client.post(base+"/calculate",headers=h,json={"rate_schedule_id":sid});assert all(again.json()["reused"].values())
 retrieved=await client.get(base+f"?rate_schedule_id={sid}",headers=h);assert retrieved.json()["cost"]["cost_hash"]==out["cost"]["cost_hash"]
 comparison=await client.get(f"/api/v1/projects/{p['id']}/versions/{v['id']}/engineering/comparison",headers=h);row=next(x for x in comparison.json()["alternatives"] if x["alternative_id"]==aid);assert row["cost_total"]==out["cost"]["total_cost"] and row["regulatory_status"]=="UNKNOWN"
 async with factory() as session:
  assert await session.scalar(select(func.count(QuantityArtifact.id)))==1
  assert await session.scalar(select(func.count(CostEstimate.id)))==1
  assert await session.scalar(select(func.count(StructuralArtifact.id)))==1
  assert await session.scalar(select(func.count(RegulatoryEvaluation.id)))==1
  assert await session.scalar(select(func.count(ValidationRun.id)))==2
  assert await session.scalar(select(func.count(ArtifactDependency.id)))==16

async def test_phase3_cross_tenant_non_disclosure_and_verified_rate_claim_rejected(api):
 client,_=api;h,org,p,v,aid=await setup(client);other,_,_,_,_=await setup(client,"other")
 denied=await client.get(f"/api/v1/projects/{p['id']}/versions/{v['id']}/design/alternatives/{aid}/engineering",headers=other);assert denied.status_code==404 and denied.json()["error"]["code"]=="PROJECT_NOT_FOUND"
 fake=await client.post("/api/v1/engineering/rate-schedules",headers=h,json={"organization_id":org["id"],"name":"Fake verified","version":"1","jurisdiction":"Riyadh","currency":"SAR","source_reference":"claim","effective_date":"2026","source_type":"VERIFIED_EXTERNAL","entries":[{"item_code":"X","category":"Other","description":"x","quantity_code":"GFA","unit":"m2","rate":1,"source_reference":"claim","effective_date":"2026"}]});assert fake.status_code==422 and fake.json()["error"]["code"]=="RATE_SOURCE_NOT_VERIFIED"
