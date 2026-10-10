from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProjectVersion, User, WorldModelRevision
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.foundation.service import resolve_project_version, resolve_world_model
from app.domains.semantic_model.service import compile_parametric_geometry, compile_semantic_model
from app.domains.semantic_model.editing import (
    _element, check_expected_revision, create_element, delete_element, edit_property, impact_groups,
    affected_elements_for_scope, downstream_elements_for_scope, load_editable_model, persist_designer_mutation, protected_elements_for_scope, redo, set_host, set_lock, state_for, undo,
)
from app.domains.semantic_model.schemas import (
    SemanticElementCreate, SemanticElementDelete, SemanticHistoryAction, SemanticLockChange,
    SemanticPropertyEdit, SemanticRegenerationRequest, SemanticHostChange,
)
from app.domains.foundation.service import audit, error

router = APIRouter(tags=["semantic-building-model"])


async def _canonical(project_id: str, version_ref: str, user: User, session: AsyncSession):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    semantic = world.model_json.get("semantic_model")
    if not isinstance(semantic, dict) or not semantic.get("elements"):
        # Backward-compatible deterministic projection for pre-Phase-24 revisions.
        semantic = compile_semantic_model(world.model_json)
    return project, version, world, semantic


@router.get("/projects/{project_id}/versions/{version_ref}/semantic-model")
async def get_semantic_model(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return the immutable semantic graph attached to the verified canonical revision."""
    project, version, world, semantic = await _canonical(project_id, version_ref, user, session)
    return {
        "project_id": project.id,
        "project_version_id": version.id,
        "world_model_revision_id": world.id,
        "world_model_revision": world.revision,
        "world_model_hash": world.model_hash,
        "semantic_model": semantic,
        "designer_state": state_for(world.model_json),
        "consistency_issues": world.model_json.get("consistency_issues", []),
    }


@router.get("/projects/{project_id}/versions/{version_ref}/semantic-model/parametric-geometry")
async def get_parametric_geometry_spec(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return deterministic CAD/BIM feature intents and explicit missing-input gates."""
    project, version, world, semantic = await _canonical(project_id, version_ref, user, session)
    spec = compile_parametric_geometry(world.model_json, semantic)
    return {
        "project_id": project.id,
        "project_version_id": version.id,
        "world_model_revision_id": world.id,
        "world_model_revision": world.revision,
        "world_model_hash": world.model_hash,
        "specification": spec,
    }



def _mutation_out(version: ProjectVersion, world: WorldModelRevision, event: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "version": {
            "id": version.id, "version_number": version.version, "status": version.status,
            "revision_number": version.revision_number,
        },
        "world_model_revision": {"id": world.id, "revision_number": world.revision, "model_hash": world.model_hash},
        "event": event,
    }


@router.get("/projects/{project_id}/versions/{version_ref}/semantic-model/designer-state")
async def get_designer_state(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    state = state_for(world.model_json)
    return {
        "project_id": project.id,
        "project_version_id": version.id,
        "version_status": version.status,
        "revision_number": version.revision_number,
        "world_model_revision_id": world.id,
        "world_model_hash": world.model_hash,
        "locks": state["locks"],
        "history": state["history"][-100:],
        "can_undo": bool(state["undo_stack"]),
        "can_redo": bool(state["redo_stack"]),
        "undo_depth": len(state["undo_stack"]),
        "redo_depth": len(state["redo_stack"]),
        "designer_element_ids": [item.get("id") for item in world.model_json.get("designer_elements", [])],
    }


@router.patch("/projects/{project_id}/versions/{version_ref}/semantic-model/elements/{element_id}")
async def edit_semantic_element(
    project_id: str,
    version_ref: str,
    element_id: str,
    body: SemanticPropertyEdit,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version, _, model, state = await load_editable_model(session, project_id, version_ref, user)
    await check_expected_revision(version, body.expected_revision)
    event = edit_property(model, state, element_id, body.property, body.value, user.id, body.reason)
    world = await persist_designer_mutation(session, project=project, version=version, user=user,
                                            model=model, action="EDIT", event=event)
    return _mutation_out(version, world, event)


@router.patch("/projects/{project_id}/versions/{version_ref}/semantic-model/elements/{element_id}/host")
async def change_semantic_element_host(
    project_id: str,
    version_ref: str,
    element_id: str,
    body: SemanticHostChange,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version, _, model, state = await load_editable_model(session, project_id, version_ref, user)
    await check_expected_revision(version, body.expected_revision)
    event = set_host(model, state, element_id, body.host_element_id, user.id, body.reason)
    world = await persist_designer_mutation(session, project=project, version=version, user=user,
                                            model=model, action="HOST_CHANGED", event=event)
    return _mutation_out(version, world, event)


@router.post("/projects/{project_id}/versions/{version_ref}/semantic-model/elements", status_code=201)
async def create_semantic_element(
    project_id: str,
    version_ref: str,
    body: SemanticElementCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version, _, model, state = await load_editable_model(session, project_id, version_ref, user)
    await check_expected_revision(version, body.expected_revision)
    event = create_element(model, state, element_type=body.element_type, name=body.name,
        properties=body.properties, level_number=body.level_number, actor_id=user.id, reason=body.reason,
        host_element_id=body.host_element_id)
    world = await persist_designer_mutation(session, project=project, version=version, user=user,
                                            model=model, action="ELEMENT_CREATED", event=event)
    return _mutation_out(version, world, event)


@router.delete("/projects/{project_id}/versions/{version_ref}/semantic-model/elements/{element_id}")
async def remove_semantic_element(
    project_id: str,
    version_ref: str,
    element_id: str,
    body: SemanticElementDelete,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version, _, model, state = await load_editable_model(session, project_id, version_ref, user)
    await check_expected_revision(version, body.expected_revision)
    event = delete_element(model, state, element_id, user.id, body.reason)
    world = await persist_designer_mutation(session, project=project, version=version, user=user,
                                            model=model, action="ELEMENT_DELETED", event=event)
    return _mutation_out(version, world, event)


@router.post("/projects/{project_id}/versions/{version_ref}/semantic-model/elements/{element_id}/lock")
async def lock_semantic_element(
    project_id: str,
    version_ref: str,
    element_id: str,
    body: SemanticLockChange,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version, _, model, state = await load_editable_model(session, project_id, version_ref, user)
    await check_expected_revision(version, body.expected_revision)
    element = _element(model, element_id)
    if state["locks"].get(element_id, {}).get("locked"):
        raise error(409, "ELEMENT_ALREADY_LOCKED", "This semantic element is already locked", element_id=element_id)
    event = set_lock(state, element_id, user.id, True, body.reason)
    model["designer_state"] = state
    world = await persist_designer_mutation(session, project=project, version=version, user=user,
                                            model=model, action="ELEMENT_LOCKED", event=event)
    return {**_mutation_out(version, world, event), "element_type": element["element_type"]}


@router.post("/projects/{project_id}/versions/{version_ref}/semantic-model/elements/{element_id}/unlock")
async def unlock_semantic_element(
    project_id: str,
    version_ref: str,
    element_id: str,
    body: SemanticLockChange,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version, _, model, state = await load_editable_model(session, project_id, version_ref, user)
    await check_expected_revision(version, body.expected_revision)
    _element(model, element_id)
    if not state["locks"].get(element_id, {}).get("locked"):
        raise error(409, "ELEMENT_NOT_LOCKED", "This semantic element is not locked", element_id=element_id)
    event = set_lock(state, element_id, user.id, False, body.reason)
    model["designer_state"] = state
    world = await persist_designer_mutation(session, project=project, version=version, user=user,
                                            model=model, action="ELEMENT_UNLOCKED", event=event)
    return _mutation_out(version, world, event)


@router.post("/projects/{project_id}/versions/{version_ref}/semantic-model/undo")
async def undo_semantic_edit(
    project_id: str,
    version_ref: str,
    body: SemanticHistoryAction,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version, _, model, state = await load_editable_model(session, project_id, version_ref, user)
    await check_expected_revision(version, body.expected_revision)
    event = undo(model, state, user.id)
    world = await persist_designer_mutation(session, project=project, version=version, user=user,
                                            model=model, action="UNDO", event=event)
    return _mutation_out(version, world, event)


@router.post("/projects/{project_id}/versions/{version_ref}/semantic-model/redo")
async def redo_semantic_edit(
    project_id: str,
    version_ref: str,
    body: SemanticHistoryAction,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version, _, model, state = await load_editable_model(session, project_id, version_ref, user)
    await check_expected_revision(version, body.expected_revision)
    event = redo(model, state, user.id)
    world = await persist_designer_mutation(session, project=project, version=version, user=user,
                                            model=model, action="REDO", event=event)
    return _mutation_out(version, world, event)


@router.get("/projects/{project_id}/versions/{version_ref}/semantic-model/regeneration-plan")
async def semantic_regeneration_plan(
    project_id: str,
    version_ref: str,
    element_id: str | None = Query(default=None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    semantic = world.model_json.get("semantic_model") or compile_semantic_model(world.model_json)
    elements = semantic.get("elements", [])
    by_id = {element["id"]: element for element in elements}
    if element_id and element_id not in by_id:
        raise error(404, "SEMANTIC_ELEMENT_NOT_FOUND", "Semantic element not found", element_id=element_id)
    if not element_id:
        affected = set(by_id)
        regeneration_candidates = set(by_id)
        groups = ["design_alternatives", "parametric_geometry_intents", "quantities", "cost",
                  "structural_review", "regulatory_review", "validation"]
    else:
        selected = by_id[element_id]
        if selected["element_type"] in {"Site", "Building"}:
            affected = set(by_id)
            regeneration_candidates = set(by_id)
        else:
            affected = affected_elements_for_scope(semantic, element_id)
            regeneration_candidates = downstream_elements_for_scope(semantic, element_id)
        prop = "length_m" if selected["element_type"] in {"Wall", "Slab", "Roof", "Door", "Window"} else (
            "floor_count" if selected["element_type"] == "Building" else "area_m2")
        groups = impact_groups(selected["element_type"], prop)
    state = state_for(world.model_json)
    locked = sorted(protected_elements_for_scope(semantic, state, regeneration_candidates))
    eligible = sorted(regeneration_candidates - set(locked))
    return {
        "project_id": project.id,
        "project_version_id": version.id,
        "world_model_hash": world.model_hash,
        "target_element_id": element_id,
        "affected_element_ids": sorted(affected),
        "regeneration_candidate_ids": sorted(regeneration_candidates),
        "eligible_element_ids": eligible,
        "protected_element_ids": locked,
        "recompute_groups": sorted(set(groups)),
        "strategy": "selective_semantic_feature_intents",
        "native_cad_generation": "not_run",
        "notice": "This plan selects semantic feature intents only. Native CAD solids and exports are produced by the separate CAD worker pipeline.",
    }


@router.post("/projects/{project_id}/versions/{version_ref}/semantic-model/regenerate")
async def regenerate_semantic_intents(
    project_id: str,
    version_ref: str,
    body: SemanticRegenerationRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    world = await resolve_world_model(session, version.id)
    if body.expected_world_model_hash != world.model_hash:
        raise error(409, "STALE_WORLD_MODEL", "The World Model changed after this regeneration request was prepared",
                    expected_hash=body.expected_world_model_hash, current_hash=world.model_hash)
    semantic = world.model_json.get("semantic_model") or compile_semantic_model(world.model_json)
    all_elements = semantic.get("elements", [])
    by_id = {element["id"]: element for element in all_elements}
    requested = set(body.element_ids) if body.element_ids else set(by_id)
    missing = sorted(requested - set(by_id))
    if missing:
        raise error(404, "SEMANTIC_ELEMENT_NOT_FOUND", "One or more semantic elements were not found", element_ids=missing)
    state = state_for(world.model_json)
    protected = sorted(protected_elements_for_scope(semantic, state, requested))
    eligible = requested - set(protected)
    selected_spec = compile_parametric_geometry(world.model_json, semantic, element_ids=eligible)
    intents = selected_spec.get("intents", [])
    status = ("ALL_TARGETS_PROTECTED" if not eligible and protected else
              "REVIEW_REQUIRED" if any(intent["status"] == "REVIEW_REQUIRED" for intent in intents) else
              "UNDERCONSTRAINED" if any(intent["status"] == "UNDERCONSTRAINED" for intent in intents) else
              "INTENT_SPEC_READY")
    specification = {
        "schema_version": selected_spec["schema_version"],
        "project_id": project.id,
        "project_version_id": version.id,
        "source_world_model_hash": world.model_hash,
        "semantic_model_hash": selected_spec["semantic_model_hash"],
        "strategy": "selective_semantic_feature_intents",
        "status": status,
        "requested_element_ids": sorted(requested),
        "regenerated_element_ids": sorted(eligible),
        "protected_element_ids": protected,
        "intents": intents,
        "limitations": selected_spec["limitations"] + [
            "This operation compiles semantic feature intents; it does not execute the native CAD worker or create B-rep/STEP/IFC/GLB artifacts."
        ],
    }
    from app.domains.semantic_model.service import canonical_hash
    specification["specification_hash"] = canonical_hash(specification)
    await audit(session, project=project, version=version, actor=user.id, action="SEMANTIC_INTENTS_REGENERATED",
        entity="semantic_model", entity_id=version.id, metadata={
            "world_model_hash": world.model_hash, "specification_hash": specification["specification_hash"],
            "requested_element_ids": sorted(requested), "regenerated_element_ids": sorted(eligible),
            "protected_element_ids": protected, "status": status,
        })
    await session.commit()
    return {"project_id": project.id, "project_version_id": version.id, "world_model_hash": world.model_hash,
            "specification": specification}
