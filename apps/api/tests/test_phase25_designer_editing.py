from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.domains.semantic_model.editing import (
    create_element,
    edit_property,
    apply_overrides,
    affected_elements_for_scope,
    downstream_elements_for_scope,
    initial_designer_state,
    set_host,
    set_lock,
    redo,
    undo,
)
from app.domains.semantic_model.service import compile_parametric_geometry, compile_semantic_model
from app.domains.semantic_model.schemas import SemanticPropertyEdit


def world_fixture() -> dict:
    model = {
        "schema_version": "1.0.0",
        "project_id": "project-phase25",
        "project_version_id": "version-phase25",
        "site": {"area": {"value": 3000.0, "unit": "m2"}, "location": {"city": "Riyadh", "country": "Saudi Arabia"}},
        "building": {
            "use": "commercial_retail", "floor_count": 2,
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
        "spaces": [], "parking": {"arrangement": "surface", "spaces": {"value": 30, "unit": "count"}},
        "properties": {}, "provenance": {}, "unknowns": [], "consistency_issues": [],
        "designer_elements": [], "designer_relationships": [], "designer_state": initial_designer_state(),
    }
    model["semantic_model"] = compile_semantic_model(model)
    return model


def semantic_element(model: dict, element_type: str, identity_key: str | None = None) -> dict:
    return next(item for item in model["semantic_model"]["elements"]
                if item["element_type"] == element_type and
                (identity_key is None or item.get("identity_key") == identity_key))


def test_edit_undo_redo_restores_values_and_hash_inputs():
    model = world_fixture()
    state = model["designer_state"]
    building = semantic_element(model, "Building")
    event = edit_property(model, state, building["id"], "footprint_width_m", 25, "designer-1", "Set measured footprint")
    assert model["properties"]["footprint_width_m"] == 25.0
    assert model["semantic_model"]["source_world_model_hash"]
    assert state["undo_stack"] == [event["event_id"]]

    undo(model, state, "designer-1")
    assert "footprint_width_m" not in model["properties"]
    assert state["redo_stack"] == [event["event_id"]]

    redo(model, state, "designer-1")
    assert model["properties"]["footprint_width_m"] == 25.0
    assert state["undo_stack"] == [event["event_id"]]
    assert [item["action"] for item in state["history"]][-2:] == ["UNDO", "REDO"]


def test_gfa_and_floor_height_edits_propagate_to_storey_inputs_and_consistency():
    model = world_fixture()
    state = model["designer_state"]
    building = semantic_element(model, "Building")
    edit_property(model, state, building["id"], "target_gfa_m2", 2400, "designer-1", "Increase target GFA")
    assert [level["area"]["value"] for level in model["levels"]] == [1200.0, 1200.0]
    edit_property(model, state, building["id"], "floor_to_floor_height_m", 4.5,
                  "designer-1", "Increase floor height")
    assert [level["elevation"]["value"] for level in model["levels"]] == [0.0, 4.5]
    assert [level["floor_to_floor_height"]["value"] for level in model["levels"]] == [4.5, 4.5]
    assert any(issue["code"] == "HEIGHT_FLOOR_INCONSISTENCY" for issue in model["consistency_issues"])


def test_locked_storey_blocks_floor_count_edit_that_would_remove_it():
    model = world_fixture()
    state = model["designer_state"]
    second = semantic_element(model, "Storey", "level:2")
    set_lock(state, second["id"], "designer-1", True, "Keep upper floor")
    model["designer_state"] = state
    building = semantic_element(model, "Building")
    with pytest.raises(HTTPException) as raised:
        edit_property(model, state, building["id"], "floor_count", 1, "designer-1", "Reduce floors")
    assert raised.value.status_code == 409
    assert raised.value.detail["error"]["code"] == "LOCKED_DEPENDENCY"
    assert model["building"]["floor_count"] == 2


def test_floor_count_cannot_orphan_authored_components():
    model = world_fixture()
    state = model["designer_state"]
    create_element(model, state, element_type="Wall", name="Upper wall",
        properties={"length_m": 5, "height_m": 3, "thickness_m": 0.2},
        level_number=2, actor_id="designer-1", reason="Create wall on upper storey")
    building = semantic_element(model, "Building")
    with pytest.raises(HTTPException) as raised:
        edit_property(model, state, building["id"], "floor_count", 1, "designer-1", "Remove upper floor")
    assert raised.value.status_code == 409
    assert raised.value.detail["error"]["code"] == "STOREY_HAS_COMPONENTS"
    assert model["building"]["floor_count"] == 2
    assert len(model["levels"]) == 2


def test_authored_wall_has_typed_properties_and_selective_feature_intent():
    model = world_fixture()
    state = model["designer_state"]
    event = create_element(model, state, element_type="Wall", name="North wall",
        properties={"length_m": 8, "height_m": 3, "thickness_m": 0.2},
        level_number=1, actor_id="designer-1", reason="Model north facade")
    wall_id = event["element_id"]
    wall = next(item for item in model["semantic_model"]["elements"] if item["id"] == wall_id)
    assert wall["designer_authored"] is True
    assert wall["properties"]["length_m"]["value"] == 8.0
    assert any(rel["source_id"] == semantic_element(model, "Storey", "level:1")["id"]
               and rel["target_id"] == wall_id for rel in model["semantic_model"]["relationships"])
    spec = compile_parametric_geometry(model, model["semantic_model"])
    intent = next(item for item in spec["intents"] if item["element_id"] == wall_id)
    assert intent["status"] == "READY_FOR_CAD_ADAPTER"
    assert intent["parameters"] == {"length_m": 8.0, "height_m": 3.0, "thickness_m": 0.2}
    selected_spec = compile_parametric_geometry(model, model["semantic_model"], element_ids={wall_id})
    assert [item["element_id"] for item in selected_spec["intents"]] == [wall_id]

    undo(model, state, "designer-1")
    assert not any(item["id"] == wall_id for item in model["semantic_model"]["elements"])
    redo(model, state, "designer-1")
    assert any(item["id"] == wall_id for item in model["semantic_model"]["elements"])



def test_architectural_component_without_storey_is_underconstrained():
    model = world_fixture()
    state = model["designer_state"]
    wall = create_element(model, state, element_type="Wall", name="Unplaced wall",
        properties={"length_m": 5, "height_m": 3, "thickness_m": 0.2},
        level_number=None, actor_id="designer-1", reason="Create wall without placement")
    intent = next(item for item in compile_parametric_geometry(model, model["semantic_model"])["intents"]
                  if item["element_id"] == wall["element_id"])
    assert intent["status"] == "UNDERCONSTRAINED"
    assert "storey_placement" in intent["missing_parameters"]

def test_openings_require_an_explicit_wall_host_and_block_host_deletion():
    model = world_fixture()
    state = model["designer_state"]
    wall_event = create_element(model, state, element_type="Wall", name="Opening wall",
        properties={"length_m": 6, "height_m": 3, "thickness_m": 0.2},
        level_number=1, actor_id="designer-1", reason="Create host wall")
    wall_id = wall_event["element_id"]
    unhosted = create_element(model, state, element_type="Door", name="Unhosted door",
        properties={"width_m": 0.9, "height_m": 2.1}, level_number=1,
        actor_id="designer-1", reason="Door without a host")
    spec = compile_parametric_geometry(model, model["semantic_model"])
    door_intent = next(item for item in spec["intents"] if item["element_id"] == unhosted["element_id"])
    assert door_intent["status"] == "UNDERCONSTRAINED"
    assert "host_wall_id" in door_intent["missing_parameters"]
    assert unhosted["element_id"] not in affected_elements_for_scope(model["semantic_model"], wall_id)
    host_event = set_host(model, state, unhosted["element_id"], wall_id, "designer-1", "Attach door to wall")
    spec = compile_parametric_geometry(model, model["semantic_model"])
    assert next(item for item in spec["intents"] if item["element_id"] == unhosted["element_id"])["status"] == "READY_FOR_CAD_ADAPTER"
    undo(model, state, "designer-1")
    spec = compile_parametric_geometry(model, model["semantic_model"])
    assert "host_wall_id" in next(item for item in spec["intents"] if item["element_id"] == unhosted["element_id"])["missing_parameters"]
    redo(model, state, "designer-1")
    assert state["history"][-1]["target_event_id"] == host_event["event_id"]

    hosted = create_element(model, state, element_type="Window", name="South window",
        properties={"width_m": 1.2, "height_m": 1.5}, level_number=1,
        host_element_id=wall_id, actor_id="designer-1", reason="Attach window to wall")
    spec = compile_parametric_geometry(model, model["semantic_model"])
    window_intent = next(item for item in spec["intents"] if item["element_id"] == hosted["element_id"])
    assert window_intent["status"] == "READY_FOR_CAD_ADAPTER"
    assert any(rel["source_id"] == wall_id and rel["target_id"] == hosted["element_id"]
               and rel["relationship_type"] == "hosts_opening"
               for rel in model["semantic_model"]["relationships"])
    affected = affected_elements_for_scope(model["semantic_model"], wall_id)
    downstream = downstream_elements_for_scope(model["semantic_model"], wall_id)
    assert wall_id in affected and hosted["element_id"] in affected
    assert semantic_element(model, "Storey", "level:1")["id"] in affected
    assert unhosted["element_id"] in affected  # the door was reattached to this wall by redo
    assert downstream == {wall_id, hosted["element_id"], unhosted["element_id"]}
    assert semantic_element(model, "Storey", "level:1")["id"] not in downstream

    with pytest.raises(HTTPException) as raised:
        from app.domains.semantic_model.editing import delete_element
        delete_element(model, state, wall_id, "designer-1", "Try deleting a wall with a hosted opening")
    assert raised.value.status_code == 409
    assert raised.value.detail["error"]["code"] == "ELEMENT_HAS_DEPENDENTS"



def test_floor_count_reduction_cannot_orphan_authored_components():
    model = world_fixture()
    state = model["designer_state"]
    create_element(model, state, element_type="Wall", name="Upper wall",
        properties={"length_m": 5, "height_m": 3, "thickness_m": 0.2},
        level_number=2, actor_id="designer-1", reason="Add upper-storey wall")
    building = semantic_element(model, "Building")
    with pytest.raises(HTTPException) as raised:
        edit_property(model, state, building["id"], "floor_count", 1, "designer-1", "Remove upper floor")
    assert raised.value.status_code == 409
    assert raised.value.detail["error"]["code"] == "STOREY_HAS_COMPONENTS"
    assert model["building"]["floor_count"] == 2


def test_rebuild_surfaces_stale_storey_override_instead_of_crashing():
    model = world_fixture()
    building = semantic_element(model, "Building")
    second = semantic_element(model, "Storey", "level:2")
    state = initial_designer_state()
    state["overrides"] = {
        # Insert the per-storey edit first to exercise dependency-safe ordering.
        f"{second['id']}:area_m2": {
            "element_id": second["id"], "element_type": "Storey", "identity_key": "level:2",
            "property": "area_m2", "value": 900, "unit": "m2", "data_type": "number",
        },
        f"{building['id']}:floor_count": {
            "element_id": building["id"], "element_type": "Building", "identity_key": "building",
            "property": "floor_count", "value": 1, "unit": "count", "data_type": "integer",
        },
    }
    apply_overrides(model, state)
    assert model["building"]["floor_count"] == 1
    assert [row["level_number"] for row in model["levels"]] == [1]
    assert any(issue["code"] == "DESIGNER_OVERRIDE_REVIEW_REQUIRED"
               and issue["element_id"] == second["id"] for issue in model["consistency_issues"])


def test_host_change_undo_redo_restores_spatial_relationships():
    model = world_fixture()
    state = model["designer_state"]
    wall = create_element(model, state, element_type="Wall", name="Host wall",
        properties={"length_m": 6, "height_m": 3, "thickness_m": 0.2},
        level_number=1, actor_id="designer-1", reason="Create host")
    door = create_element(model, state, element_type="Door", name="Door",
        properties={"width_m": 0.9, "height_m": 2.1}, level_number=1,
        actor_id="designer-1", reason="Create door")
    set_host(model, state, door["element_id"], wall["element_id"], "designer-1", "Attach to host wall")
    assert any(rel["source_id"] == wall["element_id"] and rel["target_id"] == door["element_id"]
               and rel["relationship_type"] == "hosts_opening" for rel in model["designer_relationships"])
    undo(model, state, "designer-1")
    assert not any(rel["source_id"] == wall["element_id"] and rel["target_id"] == door["element_id"]
                   and rel["relationship_type"] == "hosts_opening" for rel in model["designer_relationships"])
    assert any(rel["target_id"] == door["element_id"] and rel["relationship_type"] == "hosts_element"
               for rel in model["designer_relationships"])
    redo(model, state, "designer-1")
    assert any(rel["source_id"] == wall["element_id"] and rel["target_id"] == door["element_id"]
               and rel["relationship_type"] == "hosts_opening" for rel in model["designer_relationships"])


def test_gfa_propagation_preserves_explicit_storey_area_and_height_overrides():
    model = world_fixture()
    state = model["designer_state"]
    storey_two = semantic_element(model, "Storey", "level:2")
    edit_property(model, state, storey_two["id"], "area_m2", 900, "designer-1", "Preserve upper floor area")
    building = semantic_element(model, "Building")
    edit_property(model, state, building["id"], "target_gfa_m2", 2400, "designer-1", "Increase target GFA")
    assert next(level for level in model["levels"] if level["level_number"] == 2)["area"]["value"] == 900.0
    assert next(level for level in model["levels"] if level["level_number"] == 1)["area"]["value"] == 1500.0

    first_storey = semantic_element(model, "Storey", "level:1")
    edit_property(model, state, first_storey["id"], "floor_to_floor_height_m", 5, "designer-1", "Raise first floor")
    levels = model["levels"]
    assert levels[0]["floor_to_floor_height"]["value"] == 5.0
    assert levels[1]["elevation"]["value"] == 5.0
    assert levels[1]["floor_to_floor_height"]["value"] == 4.0
    semantic = compile_semantic_model(model)
    second_id = next(item["id"] for item in semantic["elements"]
                     if item["element_type"] == "Storey" and item["identity_key"] == "level:2")
    intent = next(item for item in compile_parametric_geometry(model, semantic)["intents"]
                  if item["element_id"] == second_id)
    assert intent["parameters"]["target_area_m2"] == 900.0
    assert intent["parameters"]["floor_to_floor_height_m"] == 4.0
    assert intent["parameters"]["elevation_m"] == 5.0


def test_undo_cannot_remove_a_locked_authored_element():
    model = world_fixture()
    state = model["designer_state"]
    wall = create_element(model, state, element_type="Wall", name="Protected wall",
        properties={"length_m": 5, "height_m": 3, "thickness_m": 0.2},
        level_number=1, actor_id="designer-1", reason="Create wall")
    set_lock(state, wall["element_id"], "designer-1", True, "Freeze reviewed wall")
    with pytest.raises(HTTPException) as raised:
        undo(model, state, "designer-1")
    assert raised.value.status_code == 409
    assert raised.value.detail["error"]["code"] == "ELEMENT_LOCKED"
    assert any(element["id"] == wall["element_id"] for element in model["semantic_model"]["elements"])


def test_designer_mutation_reason_must_not_be_whitespace():
    with pytest.raises(ValidationError):
        SemanticPropertyEdit(property="floor_count", value=3, reason="   ", expected_revision=1)


def test_requirement_rebuild_refuses_to_remove_a_locked_storey():
    model = world_fixture()
    second = semantic_element(model, "Storey", "level:2")
    state = initial_designer_state()
    state["locks"][second["id"]] = {
        "locked": True, "reason": "Keep this floor", "locked_by": "designer-1",
    }
    model["building"]["floor_count"] = 1
    model["levels"] = model["levels"][:1]
    with pytest.raises(HTTPException) as raised:
        apply_overrides(model, state)
    assert raised.value.status_code == 409
    assert raised.value.detail["error"]["code"] == "LOCKED_DEPENDENCY"


def test_requirement_rebuild_refuses_to_orphan_a_hosted_component():
    model = world_fixture()
    state = model["designer_state"]
    create_element(model, state, element_type="Wall", name="Upper-storey wall",
        properties={"length_m": 5, "height_m": 3, "thickness_m": 0.2},
        level_number=2, actor_id="designer-1", reason="Add wall on upper storey")
    model["building"]["floor_count"] = 1
    model["levels"] = model["levels"][:1]
    with pytest.raises(HTTPException) as raised:
        apply_overrides(model, state)
    assert raised.value.status_code == 409
    assert raised.value.detail["error"]["code"] == "STOREY_HAS_COMPONENTS"


def test_locked_storey_values_survive_global_gfa_and_floor_height_changes():
    model = world_fixture()
    second = semantic_element(model, "Storey", "level:2")
    state = initial_designer_state()
    state["locks"][second["id"]] = {
        "locked": True, "reason": "Keep reviewed upper floor", "locked_by": "designer-1",
    }
    model["provenance"]["building_height"] = {"source_type": "DERIVED"}
    model["building"]["target_gfa"] = {"value": 3000.0, "unit": "m2"}
    model["building"]["floor_to_floor_height"] = {"value": 5.0, "unit": "m"}
    apply_overrides(model, state)
    first, second_level = model["levels"]
    assert first["area"]["value"] == 2000.0
    assert first["floor_to_floor_height"]["value"] == 5.0
    assert first["elevation"]["value"] == 0.0
    assert second_level["area"]["value"] == 1000.0
    assert second_level["floor_to_floor_height"]["value"] == 4.0
    assert second_level["elevation"]["value"] == 4.0
    assert model["building"]["height"]["value"] == 9.0
    assert not any(issue["code"] == "HEIGHT_FLOOR_INCONSISTENCY"
                   for issue in model["consistency_issues"])


def test_locked_storey_area_mismatch_is_visible_in_cad_intents():
    model = world_fixture()
    state = initial_designer_state()
    storeys = [item for item in model["semantic_model"]["elements"] if item["element_type"] == "Storey"]
    for storey in storeys:
        state["locks"][storey["id"]] = {
            "locked": True, "reason": "Freeze reviewed floor area", "locked_by": "designer-1",
        }
    model["building"]["target_gfa"] = {"value": 3000.0, "unit": "m2"}
    apply_overrides(model, state)
    assert any(issue["code"] == "STOREY_AREA_GFA_INCONSISTENCY" for issue in model["consistency_issues"])
    spec = compile_parametric_geometry(model, model["semantic_model"])
    assert spec["status"] == "REVIEW_REQUIRED"
    assert any("sum of storey area" in warning.lower()
               for intent in spec["intents"] for warning in intent["warnings"])

def test_invalid_or_unsupported_values_are_rejected_without_mutation():
    model = world_fixture()
    state = model["designer_state"]
    building = semantic_element(model, "Building")
    with pytest.raises(HTTPException) as raised:
        edit_property(model, state, building["id"], "floor_count", 0, "designer-1", "Invalid floor count")
    assert raised.value.status_code == 422
    with pytest.raises(HTTPException) as raised:
        edit_property(model, state, building["id"], "arbitrary_sql", "x", "designer-1", "Not an editable property")
    assert raised.value.status_code == 422
    with pytest.raises(HTTPException) as raised:
        edit_property(model, state, building["id"], "floor_count", 101, "designer-1", "Implausible floor count")
    assert raised.value.status_code == 422
    assert raised.value.detail["error"]["code"] == "INVALID_PROPERTY_VALUE"
    assert model["building"]["floor_count"] == 2
    assert state["history"] == []


@pytest.mark.asyncio
async def test_api_edit_lock_undo_redo_and_override_survives_rebuild(api):
    email = f"phase25-{uuid.uuid4().hex}@example.com"
    registered = await api.post("/api/v1/auth/register", json={
        "email": email, "name": "Phase 25 Test", "password": "a-very-secure-password",
        "organization_name": "Phase 25 Test Org",
    })
    assert registered.status_code == 201, registered.text
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    orgs = (await api.get("/api/v1/organizations", headers=headers)).json()
    project_response = await api.post("/api/v1/projects", headers=headers, json={
        "organization_id": orgs[0]["id"], "name": "Designer Control Test",
        "description": "Phase 25 integration", "building_type": "commercial_retail",
        "location": "Riyadh, Saudi Arabia",
    })
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()
    versions = (await api.get(f"/api/v1/projects/{project['id']}/versions", headers=headers)).json()
    version_id = versions["current_version_id"]

    other_registered = await api.post("/api/v1/auth/register", json={
        "email": f"phase25-other-{uuid.uuid4().hex}@example.com", "name": "Other Tenant",
        "password": "a-very-secure-password", "organization_name": "Other Tenant Org",
    })
    assert other_registered.status_code == 201, other_registered.text
    other_headers = {"Authorization": f"Bearer {other_registered.json()['access_token']}"}
    cross_tenant = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/semantic-model", headers=other_headers)
    assert cross_tenant.status_code == 404

    semantic_response = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/semantic-model", headers=headers)
    assert semantic_response.status_code == 200, semantic_response.text
    building = next(item for item in semantic_response.json()["semantic_model"]["elements"]
                    if item["element_type"] == "Building")
    base = f"/api/v1/projects/{project['id']}/versions/{version_id}/semantic-model"
    edit = await api.patch(f"{base}/elements/{building['id']}", headers=headers, json={
        "property": "footprint_width_m", "value": 28, "reason": "Designer sets surveyed width",
        "expected_revision": 1,
    })
    assert edit.status_code == 200, edit.text
    assert edit.json()["version"]["revision_number"] == 2
    stale_edit = await api.patch(f"{base}/elements/{building['id']}", headers=headers, json={
        "property": "footprint_width_m", "value": 29, "reason": "Stale concurrent edit",
        "expected_revision": 1,
    })
    assert stale_edit.status_code == 409
    assert stale_edit.json()["error"]["code"] == "VERSION_CONFLICT"

    state = await api.get(f"{base}/designer-state", headers=headers)
    assert state.status_code == 200
    lock = await api.post(f"{base}/elements/{building['id']}/lock", headers=headers, json={
        "reason": "Freeze building envelope", "expected_revision": 2,
    })
    assert lock.status_code == 200, lock.text
    blocked = await api.patch(f"{base}/elements/{building['id']}", headers=headers, json={
        "property": "footprint_width_m", "value": 30, "reason": "Try protected edit",
        "expected_revision": 3,
    })
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "ELEMENT_LOCKED"

    unlock = await api.post(f"{base}/elements/{building['id']}/unlock", headers=headers, json={
        "reason": "Continue design edits", "expected_revision": 3,
    })
    assert unlock.status_code == 200, unlock.text
    undo_response = await api.post(f"{base}/undo", headers=headers, json={"expected_revision": 4})
    assert undo_response.status_code == 200, undo_response.text
    redo_response = await api.post(f"{base}/redo", headers=headers, json={"expected_revision": 5})
    assert redo_response.status_code == 200, redo_response.text

    snapshot = await api.get(f"/api/v1/projects/{project['id']}/versions/{version_id}/snapshot", headers=headers)
    assert snapshot.status_code == 200, snapshot.text
    model = snapshot.json()["world_model"]
    assert model["properties"]["footprint_width_m"] == 28.0
    assert snapshot.json()["world_model_revision"]["model_hash"]
    assert model["designer_state"]["history"][-1]["action"] == "REDO"

    # A later requirement rebuild on the same draft must not erase a designer override.
    brief = await api.post(f"/api/v1/projects/{project['id']}/versions/{version_id}/brief", headers=headers, json={
        "text": "Two-floor commercial retail building with 2,000 m2 GFA on a 3,000 m2 site.",
        "expected_revision": 6,
    })
    assert brief.status_code == 201, brief.text
    refreshed = await api.get(f"/api/v1/projects/{project['id']}/versions/{version_id}/snapshot", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["world_model"]["properties"]["footprint_width_m"] == 28.0
    floor_edit = await api.patch(f"{base}/elements/{building['id']}", headers=headers, json={
        "property": "floor_count", "value": 4, "reason": "Designer adds two levels",
        "expected_revision": 7,
    })
    assert floor_edit.status_code == 200, floor_edit.text
    assert floor_edit.json()["version"]["revision_number"] == 8

    # Designer-authored components participate in the same version-bound semantic graph.
    create_wall = await api.post(f"{base}/elements", headers=headers, json={
        "element_type": "Wall", "name": "North facade",
        "properties": {"length_m": 8, "height_m": 3, "thickness_m": 0.2},
        "level_number": 1, "reason": "Add explicit facade wall", "expected_revision": 8,
    })
    assert create_wall.status_code == 201, create_wall.text
    wall_id = create_wall.json()["event"]["element_id"]
    latest_semantic = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/semantic-model", headers=headers)
    assert latest_semantic.status_code == 200, latest_semantic.text
    plan = await api.get(f"{base}/regeneration-plan?element_id={wall_id}", headers=headers)
    assert plan.status_code == 200, plan.text
    plan_payload = plan.json()
    assert wall_id in plan_payload["affected_element_ids"]
    assert building["id"] in plan_payload["affected_element_ids"]
    assert plan_payload["regeneration_candidate_ids"] == [wall_id]
    assert plan_payload["eligible_element_ids"] == [wall_id]

    stale_regeneration = await api.post(f"{base}/regenerate", headers=headers, json={
        "element_ids": [wall_id], "expected_world_model_hash": "0" * 64,
    })
    assert stale_regeneration.status_code == 409
    assert stale_regeneration.json()["error"]["code"] == "STALE_WORLD_MODEL"
    regenerate = await api.post(f"{base}/regenerate", headers=headers, json={
        "element_ids": [wall_id],
        "expected_world_model_hash": latest_semantic.json()["world_model_hash"],
    })
    assert regenerate.status_code == 200, regenerate.text
    spec = regenerate.json()["specification"]
    assert spec["status"] == "INTENT_SPEC_READY"
    assert spec["regenerated_element_ids"] == [wall_id]
    assert len(spec["intents"]) == 1
    assert spec["intents"][0]["status"] == "READY_FOR_CAD_ADAPTER"

    create_door = await api.post(f"{base}/elements", headers=headers, json={
        "element_type": "Door", "name": "North entry",
        "properties": {"width_m": 0.9, "height_m": 2.1},
        "level_number": 1, "reason": "Add entrance opening", "expected_revision": 9,
    })
    assert create_door.status_code == 201, create_door.text
    door_id = create_door.json()["event"]["element_id"]
    host_change = await api.patch(f"{base}/elements/{door_id}/host", headers=headers, json={
        "host_element_id": wall_id, "reason": "Attach entrance to north facade",
        "expected_revision": 10,
    })
    assert host_change.status_code == 200, host_change.text
    hosted_semantic = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/semantic-model", headers=headers)
    hosted_regeneration = await api.post(f"{base}/regenerate", headers=headers, json={
        "element_ids": [door_id],
        "expected_world_model_hash": hosted_semantic.json()["world_model_hash"],
    })
    assert hosted_regeneration.status_code == 200, hosted_regeneration.text
    assert hosted_regeneration.json()["specification"]["intents"][0]["status"] == "READY_FOR_CAD_ADAPTER"

    storey_id = next(item["id"] for item in hosted_semantic.json()["semantic_model"]["elements"]
                     if item["element_type"] == "Storey" and item["identity_key"] == "level:1")
    lock_storey = await api.post(f"{base}/elements/{storey_id}/lock", headers=headers, json={
        "reason": "Protect reviewed floor and hosted components", "expected_revision": 11,
    })
    assert lock_storey.status_code == 200, lock_storey.text
    protected_edit = await api.patch(f"{base}/elements/{wall_id}", headers=headers, json={
        "property": "length_m", "value": 9, "reason": "Try to edit component in protected storey",
        "expected_revision": 12,
    })
    assert protected_edit.status_code == 409
    assert protected_edit.json()["error"]["code"] == "ELEMENT_LOCKED"
    protected_semantic = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/semantic-model", headers=headers)
    protected_regeneration = await api.post(f"{base}/regenerate", headers=headers, json={
        "element_ids": [wall_id],
        "expected_world_model_hash": protected_semantic.json()["world_model_hash"],
    })
    assert protected_regeneration.status_code == 200, protected_regeneration.text
    assert protected_regeneration.json()["specification"]["status"] == "ALL_TARGETS_PROTECTED"
    assert protected_regeneration.json()["specification"]["intents"] == []

    commit = await api.post(f"/api/v1/projects/{project['id']}/versions/{version_id}/world-model",
        headers=headers, json={"expected_revision": 12, "commit": True})
    assert commit.status_code == 200, commit.text
    immutable_edit = await api.patch(f"{base}/elements/{wall_id}", headers=headers, json={
        "property": "length_m", "value": 9, "reason": "Must not mutate committed version",
        "expected_revision": 13,
    })
    assert immutable_edit.status_code == 409
    assert immutable_edit.json()["error"]["code"] == "VERSION_IMMUTABLE"

    # New versions inherit designer-authored components, locks, and overrides,
    # while explicit version changes still take precedence over inherited facts.
    next_version_response = await api.post(f"/api/v1/projects/{project['id']}/versions",
        headers={**headers, "Idempotency-Key": f"phase25-next-{uuid.uuid4().hex}"},
        json={
            "expected_current_version_id": version_id,
            "expected_revision": 13,
            "change_summary": "Increase building to three floors",
            "changes": {"floor_count": 3},
        })
    assert next_version_response.status_code == 201, next_version_response.text
    next_version_id = next_version_response.json()["version"]["id"]
    next_snapshot = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{next_version_id}/snapshot", headers=headers)
    assert next_snapshot.status_code == 200, next_snapshot.text
    next_model = next_snapshot.json()["world_model"]
    assert next_model["building"]["floor_count"] == 3
    assert next_model["properties"]["footprint_width_m"] == 28.0
    assert any(item["id"] == wall_id for item in next_model["semantic_model"]["elements"])
    assert any(item["id"] == door_id for item in next_model["semantic_model"]["elements"])
    assert next_model["designer_state"]["locks"][storey_id]["locked"] is True
    assert next_model["designer_state"]["undo_stack"] == []
    assert next_model["designer_state"]["redo_stack"] == []


@pytest.mark.asyncio
async def test_direct_designer_mutation_invalidates_persisted_artifacts_atomically(monkeypatch):
    from types import SimpleNamespace

    from app.domains.commands import artifact_lifecycle
    from app.domains.semantic_model.editing import persist_designer_mutation

    calls = []

    async def fake_invalidate_and_enqueue(
        session,
        *,
        project,
        version,
        source_revision_hash,
        groups,
    ):
        calls.append({
            "session": session,
            "project": project,
            "version": version,
            "source_revision_hash": source_revision_hash,
            "groups": groups,
        })
        return ("artifact-design-1", "artifact-validation-1")

    monkeypatch.setattr(artifact_lifecycle, "invalidate_and_enqueue", fake_invalidate_and_enqueue)
    model = world_fixture()
    state = model["designer_state"]
    building = semantic_element(model, "Building")
    event = edit_property(
        model, state, building["id"], "floor_count", 3, "designer-1", "Add a reviewed floor"
    )
    project = SimpleNamespace(id="project-phase25", organization_id="org-phase25")
    version = SimpleNamespace(id="version-phase25", revision_number=0)
    user = SimpleNamespace(id="designer-1")

    class Session:
        def __init__(self):
            self.rows = []

        async def scalar(self, statement):
            return 0

        def add(self, row):
            self.rows.append(row)

        async def flush(self):
            return None

        async def commit(self):
            return None

    session = Session()
    revision = await persist_designer_mutation(
        session,
        project=project,
        version=version,
        user=user,
        model=model,
        action="EDIT",
        event=event,
    )

    assert revision.model_hash
    assert version.revision_number == 1
    assert len(calls) == 1
    assert calls[0]["session"] is session
    assert calls[0]["project"] is project
    assert calls[0]["version"] is version
    assert calls[0]["source_revision_hash"] == revision.model_hash
    assert "program" in calls[0]["groups"]
    assert "design_alternatives" in calls[0]["groups"]
    assert "validation" in calls[0]["groups"]
