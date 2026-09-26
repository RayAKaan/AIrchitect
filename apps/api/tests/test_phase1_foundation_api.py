import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.session import get_session
from app.main import app


@pytest.fixture
async def api():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


async def register(api, suffix="a"):
    response = await api.post("/api/v1/auth/register", json={"email": f"{suffix}-{uuid.uuid4().hex}@example.com",
        "name": "Phase One User", "password": "a-very-secure-password", "organization_name": f"Org {suffix}"})
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    organization = (await api.get("/api/v1/organizations", headers=headers)).json()[0]
    return headers, organization


async def create_project(api, headers, organization):
    response = await api.post("/api/v1/projects", headers=headers, json={"organization_id": organization["id"],
        "name": "Riyadh Retail Center", "description": "Phase 1 canonical building",
        "building_type": "commercial_retail", "location": "Riyadh, Saudi Arabia"})
    assert response.status_code == 201, response.text
    return response.json()


async def test_project_creation_is_transactional_and_has_empty_canonical_v1(api):
    headers, organization = await register(api)
    project = await create_project(api, headers, organization)
    versions = (await api.get(f"/api/v1/projects/{project['id']}/versions", headers=headers)).json()
    assert versions["current_version_id"]
    assert versions["versions"][0]["label"] == "V1"
    snapshot = (await api.get(f"/api/v1/projects/{project['id']}/versions/1/snapshot", headers=headers)).json()
    assert snapshot["world_model"]["site"]["area"] is None
    assert "site.area" in snapshot["world_model"]["unknowns"]
    assert snapshot["world_model_revision"]["model_hash"]
    audit = (await api.get(f"/api/v1/projects/{project['id']}/audit-events", headers=headers)).json()["events"]
    assert {event["action"] for event in audit} >= {"PROJECT_CREATED", "VERSION_CREATED", "WORLD_MODEL_REVISED"}


async def test_brief_requirements_assumptions_world_model_and_provenance(api):
    headers, organization = await register(api)
    project = await create_project(api, headers, organization)
    versions = (await api.get(f"/api/v1/projects/{project['id']}/versions", headers=headers)).json()
    v1 = versions["versions"][0]
    brief = ("Six-floor commercial retail building in Riyadh, approximately 18,000 m² GFA "
             "on a 3,000 m² site, basement parking.")
    response = await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/brief", headers=headers,
        json={"text": brief, "expected_revision": 1})
    assert response.status_code == 201, response.text
    payload = response.json()
    by_parameter = {item["parameter"]: item for item in payload["requirements"]}
    assert by_parameter["floor_count"]["normalized_value"] == 6
    assert by_parameter["floor_count"]["unit"] == "count"
    assert by_parameter["target_gfa"]["normalized_value"] == 18000
    assert by_parameter["site_area"]["normalized_value"] == 3000
    assert by_parameter["city"]["normalized_value"] == "Riyadh"
    assert by_parameter["building_use"]["normalized_value"] == "commercial_retail"
    assert by_parameter["parking_arrangement"]["normalized_value"] == "basement"
    assert all(item["source_type"] == "USER_BRIEF" for item in payload["requirements"])
    assumptions = (await api.get(
        f"/api/v1/projects/{project['id']}/versions/{v1['id']}/assumptions", headers=headers)).json()["assumptions"]
    assumption_map = {item["parameter"]: item for item in assumptions}
    assert assumption_map["floor_to_floor_height"]["value"] == 5.0
    assert assumption_map["floor_to_floor_height"]["status"] == "proposed"
    assert assumption_map["structural_system"]["value"] == "reinforced_concrete_frame"
    world = (await api.get(
        f"/api/v1/projects/{project['id']}/versions/{v1['id']}/world-model", headers=headers)).json()
    assert world["world_model"]["building"]["floor_count"] == 6
    assert len(world["world_model"]["levels"]) == 6
    assert world["world_model"]["building"]["target_gfa"] == {"value": 18000.0, "unit": "m2"}
    assert world["world_model"]["provenance"]["floor_count"]["source_type"] == "USER_BRIEF"
    assert world["world_model"]["provenance"]["floor_to_floor_height"]["source_type"] == "SYSTEM_ASSUMPTION"


async def test_requirement_confirmation_edit_and_optimistic_conflict(api):
    headers, organization = await register(api)
    project = await create_project(api, headers, organization)
    v1 = (await api.get(f"/api/v1/projects/{project['id']}/versions", headers=headers)).json()["versions"][0]
    brief = await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/brief", headers=headers,
        json={"text": "Commercial retail building in Riyadh with 6 floors and 18,000 m2 GFA.", "expected_revision": 1})
    data = brief.json(); floor = next(r for r in data["requirements"] if r["parameter"] == "floor_count")
    revision = data["version_revision"]
    confirm = await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/requirements/{floor['id']}/confirm",
        headers=headers, json={"decision": "CONFIRMED", "expected_revision": revision})
    assert confirm.status_code == 200
    revision = confirm.json()["version_revision"]
    edit = await api.patch(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/requirements/{floor['id']}",
        headers=headers, json={"value": 7, "unit": "count", "reason": "Client correction", "expected_revision": revision})
    assert edit.status_code == 201
    assert edit.json()["requirement"]["supersedes_id"] == floor["id"]
    stale = await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/requirements/{floor['id']}/confirm",
        headers=headers, json={"decision": "CONFIRMED", "expected_revision": revision})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"


async def test_commit_v1_create_v2_compare_and_preserve_v1(api):
    headers, organization = await register(api)
    project = await create_project(api, headers, organization)
    v1 = (await api.get(f"/api/v1/projects/{project['id']}/versions", headers=headers)).json()["versions"][0]
    brief = await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/brief", headers=headers,
        json={"text": "Six-floor commercial retail building in Riyadh with 18,000 m2 GFA on a 3,000 m2 site and basement parking.",
              "expected_revision": 1})
    revision = brief.json()["version_revision"]
    committed = await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/world-model", headers=headers,
        json={"expected_revision": revision, "commit": True})
    assert committed.status_code == 200, committed.text
    v1_committed = committed.json()["version"]
    before = (await api.get(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/snapshot", headers=headers)).json()
    created = await api.post(f"/api/v1/projects/{project['id']}/versions", headers={**headers, "Idempotency-Key": "floor-change-0001"},
        json={"expected_current_version_id": v1["id"], "expected_revision": v1_committed["revision_number"],
              "change_summary": "Increase floor count from 6 to 8", "changes": {"floor_count": 8}})
    assert created.status_code == 201, created.text
    v2 = created.json()["version"]
    retry = await api.post(f"/api/v1/projects/{project['id']}/versions", headers={**headers, "Idempotency-Key": "floor-change-0001"},
        json={"expected_current_version_id": v1["id"], "expected_revision": v1_committed["revision_number"],
              "change_summary": "Increase floor count from 6 to 8", "changes": {"floor_count": 8}})
    assert retry.status_code == 201 and retry.json()["created"] is False and retry.json()["version"]["id"] == v2["id"]
    after_v1 = (await api.get(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/snapshot", headers=headers)).json()
    snapshot_v2 = (await api.get(f"/api/v1/projects/{project['id']}/versions/{v2['id']}/snapshot", headers=headers)).json()
    assert before["world_model_revision"]["model_hash"] == after_v1["world_model_revision"]["model_hash"]
    assert after_v1["world_model"]["building"]["floor_count"] == 6
    assert snapshot_v2["world_model"]["building"]["floor_count"] == 8
    comparison = (await api.get(f"/api/v1/projects/{project['id']}/versions/compare",
        headers=headers, params={"version_a": v1["id"], "version_b": v2["id"]})).json()
    floor_change = next(change for change in comparison["changes"] if change["parameter"] == "building.floor_count")
    assert floor_change == {"parameter": "building.floor_count", "old": 6, "new": 8}
    audit = (await api.get(f"/api/v1/projects/{project['id']}/audit-events", headers=headers)).json()["events"]
    assert any(event["action"] == "REQUIREMENT_CHANGED" and event["project_version_id"] == v2["id"] for event in audit)


async def test_partial_brief_preserves_unknown_as_null_not_zero(api):
    headers, organization = await register(api)
    project = await create_project(api, headers, organization)
    v1 = (await api.get(f"/api/v1/projects/{project['id']}/versions", headers=headers)).json()["versions"][0]
    response = await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/brief", headers=headers,
        json={"text": "I want a commercial building in Riyadh.", "expected_revision": 1})
    assert response.status_code == 201
    snapshot = (await api.get(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/snapshot", headers=headers)).json()
    assert snapshot["world_model"]["site"]["area"] is None
    assert snapshot["world_model"]["building"]["floor_count"] is None
    assert snapshot["world_model"]["building"]["target_gfa"] is None
    assert "site.area" in snapshot["world_model"]["unknowns"]


async def test_contradictory_requirements_block_commit(api):
    headers, organization = await register(api)
    project = await create_project(api, headers, organization)
    v1 = (await api.get(f"/api/v1/projects/{project['id']}/versions", headers=headers)).json()["versions"][0]
    response = await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/brief", headers=headers,
        json={"text": "Commercial building in Riyadh with 6 floors, later changed in the same brief to 8 floors.",
              "expected_revision": 1})
    assert response.status_code == 201
    assert {r["status"] for r in response.json()["requirements"] if r["parameter"] == "floor_count"} == {"CONTRADICTORY"}
    commit = await api.post(f"/api/v1/projects/{project['id']}/versions/{v1['id']}/world-model", headers=headers,
        json={"expected_revision": response.json()["version_revision"], "commit": True})
    assert commit.status_code == 409
    assert commit.json()["error"]["code"] == "CONTRADICTORY_REQUIREMENTS"


async def test_client_owned_geometry_bypass_is_disabled(api):
    headers, organization = await register(api)
    project = await create_project(api, headers, organization)
    response = await api.post("/api/v1/geometry/generate", headers=headers, json={"project_id": project["id"],
        "source_revision": 1, "footprint_width_m": 50, "footprint_depth_m": 40,
        "options": [{"option_id": "injected", "floors": 99}]})
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "CANONICAL_VERSION_REQUIRED"


async def test_cross_tenant_project_access_is_non_disclosing(api):
    headers_a, org_a = await register(api, "a")
    project = await create_project(api, headers_a, org_a)
    headers_b, _ = await register(api, "b")
    response = await api.get(f"/api/v1/projects/{project['id']}/versions", headers=headers_b)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
