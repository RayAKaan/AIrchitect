from __future__ import annotations

import uuid

import pytest

from app.domains.semantic_model.service import (
    canonical_hash,
    compile_parametric_geometry,
    compile_semantic_model,
)


def sample_world_model() -> dict:
    return {
        "schema_version": "1.0.0",
        "project_id": "project-123",
        "project_version_id": "version-456",
        "site": {
            "area": {"value": 3000.0, "unit": "m2"},
            "location": {"city": "Riyadh", "country": "Saudi Arabia"},
        },
        "building": {
            "use": "commercial_retail",
            "floor_count": 2,
            "height": {"value": 8.0, "unit": "m"},
            "floor_to_floor_height": {"value": 4.0, "unit": "m"},
            "target_gfa": {"value": 2000.0, "unit": "m2"},
        },
        "levels": [
            {"level_number": 1, "name": "Level 1", "elevation": {"value": 0, "unit": "m"},
             "floor_to_floor_height": {"value": 4, "unit": "m"}, "area": {"value": 1000, "unit": "m2"}},
            {"level_number": 2, "name": "Level 2", "elevation": {"value": 4, "unit": "m"},
             "floor_to_floor_height": {"value": 4, "unit": "m"}, "area": {"value": 1000, "unit": "m2"}},
        ],
        "spaces": [],
        "parking": {"arrangement": "surface", "spaces": {"value": 30, "unit": "count"}},
        "properties": {},
        "provenance": {
            "floor_count": {"source_type": "USER_BRIEF", "source_id": "req-1", "confirmed": True},
        },
        "unknowns": ["site.width", "site.depth"],
        "semantic_model": {},
    }


def test_semantic_graph_is_deterministic_typed_and_version_bound():
    world = sample_world_model()
    first = compile_semantic_model(world)
    second = compile_semantic_model(world)
    assert first == second
    assert first["schema_version"] == "1.0.0"
    assert first["project_id"] == world["project_id"]
    assert first["project_version_id"] == world["project_version_id"]
    assert first["source_world_model_hash"] == canonical_hash({k: v for k, v in world.items() if k != "semantic_model"})
    assert first["element_types_present"] == ["Building", "ParkingFacility", "Site", "Storey"]
    assert len([e for e in first["elements"] if e["element_type"] == "Storey"]) == 2
    assert all("cad_mapping" in element and "provenance" in element for element in first["elements"])
    assert {r["relationship_type"] for r in first["relationships"]} >= {"located_on", "has_storey", "includes_facility"}
    element_ids = {element["id"] for element in first["elements"]}
    assert all(rel["source_id"] in element_ids and rel["target_id"] in element_ids for rel in first["relationships"])


def test_semantic_identity_survives_value_edits_but_source_hash_changes():
    original = sample_world_model()
    changed = sample_world_model()
    changed["building"]["height"] = {"value": 9.0, "unit": "m"}
    a = compile_semantic_model(original)
    b = compile_semantic_model(changed)
    ids_a = {(e["element_type"], e["identity_key"]): e["id"] for e in a["elements"]}
    ids_b = {(e["element_type"], e["identity_key"]): e["id"] for e in b["elements"]}
    assert ids_a == ids_b
    assert a["source_world_model_hash"] != b["source_world_model_hash"]


def test_compiler_does_not_invent_architectural_components_or_geometry():
    world = sample_world_model()
    semantic = compile_semantic_model(world)
    assert not any(e["element_type"] in {"Wall", "Slab", "Roof", "Door", "Window"} for e in semantic["elements"])
    assert set(semantic["element_types_not_modelled"]) == {"Wall", "Slab", "Roof", "Door", "Window"}
    spec = compile_parametric_geometry(world, semantic)
    assert spec["status"] == "UNDERCONSTRAINED"
    building_intent = next(i for i in spec["intents"] if i["element_type"] == "Building")
    assert set(building_intent["missing_parameters"]) >= {"footprint_width_m", "footprint_depth_m"}
    assert "not a generated B-rep or IFC file" in " ".join(spec["limitations"])
    assert spec == compile_parametric_geometry(world, semantic)


def test_explicit_footprint_dimensions_unlock_deterministic_building_and_storey_intents():
    world = sample_world_model()
    world["properties"] = {"footprint_width_m": 25.0, "footprint_depth_m": 20.0}
    semantic = compile_semantic_model(world)
    spec = compile_parametric_geometry(world, semantic)
    building_intent = next(i for i in spec["intents"] if i["element_type"] == "Building")
    storey_intents = [i for i in spec["intents"] if i["element_type"] == "Storey"]
    assert building_intent["status"] == "READY_FOR_CAD_ADAPTER"
    assert building_intent["parameters"] == {
        "footprint_width_m": 25.0,
        "footprint_depth_m": 20.0,
        "floor_count": 2,
        "floor_to_floor_height_m": 4.0,
    }
    assert len(storey_intents) == 2
    assert all(i["status"] == "READY_FOR_CAD_ADAPTER" for i in storey_intents)


@pytest.mark.asyncio
async def test_semantic_model_is_persisted_and_served_from_canonical_revision(api):
    email = f"phase24-{uuid.uuid4().hex}@example.com"
    registered = await api.post("/api/v1/auth/register", json={
        "email": email,
        "name": "Phase 24 Test",
        "password": "a-very-secure-password",
        "organization_name": "Phase 24 Test Org",
    })
    assert registered.status_code == 201, registered.text
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    orgs = (await api.get("/api/v1/organizations", headers=headers)).json()
    project_response = await api.post("/api/v1/projects", headers=headers, json={
        "organization_id": orgs[0]["id"],
        "name": "Semantic World Model Test",
        "description": "Phase 24 integration",
        "building_type": "commercial_retail",
        "location": "Riyadh, Saudi Arabia",
    })
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()
    versions = (await api.get(f"/api/v1/projects/{project['id']}/versions", headers=headers)).json()
    version_id = versions["versions"][0]["id"]
    brief = await api.post(f"/api/v1/projects/{project['id']}/versions/{version_id}/brief", headers=headers, json={
        "text": "Six-floor commercial retail building in Riyadh with 18,000 m2 GFA on a 3,000 m2 site and surface parking.",
        "expected_revision": 1,
    })
    assert brief.status_code == 201, brief.text

    semantic_response = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/semantic-model", headers=headers)
    assert semantic_response.status_code == 200, semantic_response.text
    semantic_payload = semantic_response.json()
    semantic = semantic_payload["semantic_model"]
    assert semantic_payload["world_model_hash"]
    assert semantic["source_world_model_hash"]
    assert {"Building", "Site", "Storey", "ParkingFacility"} <= set(semantic["element_types_present"])
    assert len([e for e in semantic["elements"] if e["element_type"] == "Storey"]) == 6

    geometry_response = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/semantic-model/parametric-geometry", headers=headers)
    assert geometry_response.status_code == 200, geometry_response.text
    spec = geometry_response.json()["specification"]
    assert spec["status"] == "UNDERCONSTRAINED"
    assert spec["source_world_model_hash"] == semantic["source_world_model_hash"]
    assert spec["specification_hash"]

    snapshot = await api.get(f"/api/v1/projects/{project['id']}/versions/{version_id}/snapshot", headers=headers)
    assert snapshot.status_code == 200, snapshot.text
    canonical = snapshot.json()["world_model"]
    assert canonical["semantic_model"] == semantic
    assert snapshot.json()["world_model_revision"]["model_hash"] == canonical_hash(canonical)

    other = await api.post("/api/v1/auth/register", json={
        "email": f"phase24-other-{uuid.uuid4().hex}@example.com",
        "name": "Other Tenant",
        "password": "a-very-secure-password",
        "organization_name": "Other Tenant Org",
    })
    assert other.status_code == 201, other.text
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    forbidden = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/semantic-model", headers=other_headers)
    assert forbidden.status_code == 404
