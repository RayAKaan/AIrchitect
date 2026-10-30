from types import SimpleNamespace

import pytest

from app.domains.commands.executor import execute_semantic_command
from app.domains.commands.preview import preview_command
from app.domains.commands.schemas import CommandEnvelope
from app.domains.envelope.schemas import EnvelopeRequest, PlanningRule
from app.domains.envelope.service import build_envelope, effective_envelope_request
from app.domains.semantic_model.editing import initial_designer_state, redo, undo
from app.domains.semantic_model.service import compile_semantic_model


def model_fixture():
    model = {
        "project_id": "setback-project",
        "project_version_id": "setback-version",
        "site": {
            "area": {"value": 10000.0, "unit": "m2"},
            "width": {"value": 100.0, "unit": "m"},
            "depth": {"value": 100.0, "unit": "m"},
            "location": {},
        },
        "building": {
            "use": "office",
            "floor_count": 1,
            "height": {"value": 4.0, "unit": "m"},
            "floor_to_floor_height": {"value": 4.0, "unit": "m"},
            "target_gfa": {"value": 400.0, "unit": "m2"},
            "coverage": 0.04,
        },
        "levels": [{
            "level_number": 1,
            "elevation": {"value": 0.0, "unit": "m"},
            "floor_to_floor_height": {"value": 4.0, "unit": "m"},
            "area": {"value": 400.0, "unit": "m2"},
        }],
        "spaces": [],
        "properties": {},
        "provenance": {},
        "designer_state": initial_designer_state(),
    }
    model["semantic_model"] = compile_semantic_model(model)
    return model


def change_setback_command(value):
    return CommandEnvelope(
        command_id="change-setback-1",
        type="ChangeSetback",
        schema_version=1,
        project_id="setback-project",
        version_id="setback-version",
        base_revision_hash="world-hash-1",
        idempotency_key="change-setback-key-1",
        mode="commit",
        reason="Set the preliminary design setback",
        payload={"setback_m": value},
    )


def test_change_setback_persists_non_regulatory_design_parameter_with_history():
    model = model_fixture()
    state = model["designer_state"]
    command = change_setback_command(7.5)

    preview = preview_command(command.model_copy(update={"mode": "preview"}))
    assert preview.accepted is True
    assert preview.executable is True

    result = execute_semantic_command(model, state, command, "actor-1", "world-hash-1")

    assert result.status == "committed"
    assert model["properties"]["setback_m"] == 7.5
    site = next(item for item in model["semantic_model"]["elements"] if item["element_type"] == "Site")
    assert site["properties"]["setback_m"]["value"] == 7.5
    provenance = model["provenance"][f"designer:{site['id']}:setback_m"]
    assert provenance["source_type"] == "USER_DESIGN_PARAMETER"
    assert provenance["confirmed"] is False
    assert provenance["authority"] == "NONE"

    undo(model, state, "actor-1")
    assert "setback_m" not in model["properties"]
    redo(model, state, "actor-1")
    assert model["properties"]["setback_m"] == 7.5


def test_canonical_setback_overrides_request_as_unverified_design_parameter():
    body = EnvelopeRequest(
        setback_m=PlanningRule(value=2.0, unit="m", source="OFFICIAL_RULE", status="VERIFIED")
    )
    world = SimpleNamespace(model_json={"properties": {"setback_m": 7.5}})
    effective = effective_envelope_request(body, world)

    assert effective.setback_m.value == 7.5
    assert effective.setback_m.source == "USER_DESIGN_PARAMETER"
    assert effective.setback_m.status == "DESIGN_PARAMETER"
    assert "not verified planning regulation" in effective.setback_m.applicability


def test_envelope_geometry_and_evidence_use_the_canonical_setback():
    boundary = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001], [0, 0]]],
    }
    body = EnvelopeRequest()
    world = SimpleNamespace(model_json={"properties": {"setback_m": 7.5}})
    effective = effective_envelope_request(body, world)

    result = build_envelope(boundary, effective)

    assert result["setback_m"] == 7.5
    assert result["planning_evidence"]["setback"]["source"] == "USER_DESIGN_PARAMETER"
    assert result["planning_evidence"]["setback"]["status"] == "DESIGN_PARAMETER"


def add_level_command(building_id, elevation_m):
    return CommandEnvelope(
        command_id="add-level-1",
        type="AddLevel",
        schema_version=1,
        project_id="setback-project",
        version_id="setback-version",
        base_revision_hash="world-hash-1",
        idempotency_key="add-level-key-1",
        mode="commit",
        reason="Add a new upper storey",
        payload={"building_id": building_id, "elevation_m": elevation_m},
    )


def test_add_level_updates_floor_count_and_elevation_as_one_undoable_event():
    from app.domains.semantic_model.editing import redo, undo

    model = model_fixture()
    state = model["designer_state"]
    building = next(item for item in model["semantic_model"]["elements"] if item["element_type"] == "Building")
    command = add_level_command(building["id"], 4.5)

    preview = preview_command(command.model_copy(update={"mode": "preview"}))
    assert preview.accepted is True
    assert preview.executable is True

    result = execute_semantic_command(model, state, command, "actor-1", "world-hash-1")

    assert result.status == "committed"
    assert result.event["action"] == "BATCH_EDIT"
    assert len(state["undo_stack"]) == 1
    assert model["building"]["floor_count"] == 2
    assert len(model["levels"]) == 2
    assert model["levels"][1]["elevation"]["value"] == 4.5
    assert model["levels"][0]["floor_to_floor_height"]["value"] == 4.5

    undo(model, state, "actor-1")
    assert model["building"]["floor_count"] == 1
    assert len(model["levels"]) == 1
    assert model["levels"][0]["floor_to_floor_height"]["value"] == 4.0

    redo(model, state, "actor-1")
    assert model["building"]["floor_count"] == 2
    assert len(model["levels"]) == 2
    assert model["levels"][1]["elevation"]["value"] == 4.5


def test_add_level_rejects_non_increasing_elevation_without_partial_mutation():
    model = model_fixture()
    state = model["designer_state"]
    building = next(item for item in model["semantic_model"]["elements"] if item["element_type"] == "Building")

    with pytest.raises(ValueError, match="INVALID_NEW_LEVEL_ELEVATION"):
        execute_semantic_command(
            model, state, add_level_command(building["id"], 0.0), "actor-1", "world-hash-1"
        )

    assert model["building"]["floor_count"] == 1
    assert len(model["levels"]) == 1
    assert state["history"] == []


def test_add_level_is_atomic_when_the_existing_top_storey_is_locked():
    from fastapi import HTTPException

    model = model_fixture()
    state = model["designer_state"]
    building = next(item for item in model["semantic_model"]["elements"] if item["element_type"] == "Building")
    top_storey = next(item for item in model["semantic_model"]["elements"] if item["element_type"] == "Storey")
    state["locks"][top_storey["id"]] = {"locked": True, "actor_id": "reviewer", "reason": "approved storey"}

    with pytest.raises(HTTPException) as raised:
        execute_semantic_command(
            model, state, add_level_command(building["id"], 4.5), "actor-1", "world-hash-1"
        )

    assert raised.value.status_code == 409
    assert model["building"]["floor_count"] == 1
    assert len(model["levels"]) == 1
    assert state["history"] == []
