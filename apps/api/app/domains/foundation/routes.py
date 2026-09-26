from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssumptionRecord, AuditEvent, BuildingBriefRecord, ProjectVersion, RequirementRecord, User,
    WorldModelRevision,
)
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.lifecycle.service import canonical_hash
from app.domains.requirements.extractor import DeterministicRequirementExtractor
from .schemas import (
    AssumptionIn, AssumptionPatch, BriefIn, RequirementDecision, RequirementEdit, VersionCreate,
    WorldModelCommit,
)
from .service import (
    ACTIVE_REQUIREMENT_STATES, audit, create_next_version, error, persist_world_model, resolve_project,
    resolve_project_version, resolve_world_model,
)

router = APIRouter(tags=["foundation"])
extractor = DeterministicRequirementExtractor()


def version_out(version: ProjectVersion) -> dict[str, Any]:
    return {"id": version.id, "project_id": version.project_id, "version_number": version.version,
        "label": f"V{version.version}", "status": version.status, "revision_number": version.revision_number,
        "parent_version_id": version.parent_version_id, "change_summary": version.change_summary,
        "source": version.source, "metadata": version.metadata_json, "created_by": version.created_by,
        "created_at": version.created_at}


def requirement_out(row: RequirementRecord) -> dict[str, Any]:
    return {"id": row.id, "category": row.category, "parameter": row.parameter, "source_text": row.source_text,
        "raw_value": row.raw_value_json, "normalized_value": row.normalized_value_json, "value_type": row.value_type,
        "unit": row.unit, "source_type": row.source_type, "source_reference": row.source_reference,
        "confidence": row.confidence, "status": row.status, "extraction_method": row.extraction_method,
        "confirmed_by": row.confirmed_by, "confirmed_at": row.confirmed_at, "supersedes_id": row.supersedes_id,
        "provenance": row.provenance_json, "created_at": row.created_at, "updated_at": row.updated_at}


def assumption_out(row: AssumptionRecord) -> dict[str, Any]:
    return {"id": row.id, "parameter": row.parameter, "value": row.value_json.get("value"), "unit": row.unit,
        "reason": row.reason, "source": row.source, "status": row.status, "confidence": row.confidence,
        "impact_scope": row.impact_scope_json, "supersedes_id": row.supersedes_id, "created_by": row.created_by,
        "created_at": row.created_at}


async def check_revision(version: ProjectVersion, expected: int) -> None:
    if version.revision_number != expected:
        raise error(409, "VERSION_CONFLICT", "The project version changed since it was read",
            expected_revision=expected, current_revision=version.revision_number)


@router.get("/projects/{project_id}/versions")
async def list_versions(project_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project, _ = await resolve_project(session, project_id, user.id)
    rows = (await session.scalars(select(ProjectVersion).where(ProjectVersion.project_id == project.id).order_by(ProjectVersion.version.desc()))).all()
    return {"current_version_id": project.current_version_id, "versions": [version_out(row) for row in rows]}


@router.post("/projects/{project_id}/versions", status_code=201)
async def create_version(project_id: str, body: VersionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    allowed = {"floor_count", "target_gfa", "site_area", "floor_to_floor_height", "building_height",
        "parking_spaces", "parking_arrangement", "building_use", "city"}
    unsupported = sorted(set(body.changes) - allowed)
    if unsupported:
        raise error(422, "INVALID_REQUIREMENT", "Unsupported canonical change parameters", parameters=unsupported)
    version, world, created = await create_next_version(session, project_id, user,
        expected_current_version_id=body.expected_current_version_id, expected_revision=body.expected_revision,
        change_summary=body.change_summary, changes=body.changes, idempotency_key=idempotency_key)
    if created: await session.commit()
    return {"created": created, "version": version_out(version), "world_model_revision": {
        "id": world.id, "revision_number": world.revision, "model_hash": world.model_hash}}


@router.get("/projects/{project_id}/versions/compare")
async def compare_versions(project_id: str, version_a: str = Query(), version_b: str = Query(),
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    _, a = await resolve_project_version(session, project_id, version_a, user.id)
    _, b = await resolve_project_version(session, project_id, version_b, user.id)
    wa, wb = await resolve_world_model(session, a.id), await resolve_world_model(session, b.id)

    def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
        result: dict[str, Any] = {}
        if isinstance(value, dict):
            for key, item in value.items(): result.update(flatten(item, f"{prefix}.{key}" if prefix else key))
        elif isinstance(value, list):
            # Levels/spaces are semantic collections; preserve them as values rather than comparing row IDs.
            result[prefix] = value
        else: result[prefix] = value
        return result
    left, right = flatten(wa.model_json), flatten(wb.model_json)
    ignored = {"project_version_id", "requirement_ids", "assumption_ids"}
    changes = [{"parameter": key, "old": left.get(key), "new": right.get(key)} for key in sorted(set(left) | set(right))
        if key not in ignored and not key.startswith("provenance.") and key != "consistency_issues"
        and left.get(key) != right.get(key)]
    return {"project_id": project_id, "version_a": version_out(a), "version_b": version_out(b), "changes": changes}


@router.get("/projects/{project_id}/versions/{version_ref}")
async def get_version(project_id: str, version_ref: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    return {"project": {"id": project.id, "name": project.name, "current_version_id": project.current_version_id},
        "version": version_out(version)}


@router.post("/projects/{project_id}/versions/{version_ref}/brief", status_code=201)
async def submit_version_brief(project_id: str, version_ref: str, body: BriefIn,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    await check_revision(version, body.expected_revision)
    if version.status != "DRAFT": raise error(409, "VERSION_CONFLICT", "Committed or superseded versions are immutable")
    candidates = extractor.extract(body.text)
    brief_revision = (await session.scalar(select(func.max(BuildingBriefRecord.revision)).where(
        BuildingBriefRecord.project_version_id == version.id)) or 0) + 1
    structured = {c.parameter: {"value": c.normalized_value, "unit": c.unit} for c in candidates}
    brief = BuildingBriefRecord(organization_id=project.organization_id, project_id=project.id,
        project_version_id=version.id, revision=brief_revision, raw_text=body.text, structured_json=structured,
        source_type="USER_BRIEF", source_reference=body.source_reference, content_hash=canonical_hash(body.text), created_by=user.id)
    session.add(brief); await session.flush()
    by_parameter: dict[str, set[str]] = {}
    for candidate in candidates: by_parameter.setdefault(candidate.parameter, set()).add(str(candidate.normalized_value))
    created: list[RequirementRecord] = []
    for candidate in candidates:
        contradictory = len(by_parameter[candidate.parameter]) > 1
        row = RequirementRecord(organization_id=project.organization_id, project_id=project.id,
            project_version_id=version.id, source_text=candidate.source_text, parameter=candidate.parameter,
            category=candidate.category, raw_value_json=candidate.raw_value,
            extracted_value_json=candidate.normalized_value, normalized_value_json=candidate.normalized_value,
            value_type=candidate.value_type, unit=candidate.unit, source_type="USER_BRIEF", source_reference=brief.id,
            extraction_method=candidate.extraction_method, confidence=candidate.confidence,
            status="CONTRADICTORY" if contradictory else "EXTRACTED",
            contradiction_group=candidate.parameter if contradictory else None,
            provenance_json={"brief_id": brief.id, "brief_hash": brief.content_hash}, created_by=user.id)
        session.add(row); await session.flush(); created.append(row)
        await audit(session, project=project, version=version, actor=user.id, action="REQUIREMENT_EXTRACTED",
            entity="requirement", entity_id=row.id, metadata={"parameter": row.parameter, "source_type": row.source_type})
    existing_assumptions = set((await session.scalars(select(AssumptionRecord.parameter).where(
        AssumptionRecord.project_version_id == version.id))).all())
    extracted_parameters = {c.parameter for c in candidates}
    defaults = []
    if "floor_to_floor_height" not in extracted_parameters and "floor_to_floor_height" not in existing_assumptions:
        defaults.append(("floor_to_floor_height", 5.0, "m", "Preliminary commercial-building assumption",
            ["geometry", "quantities", "cost", "structure", "regulatory"]))
    if "structural_system" not in extracted_parameters and "structural_system" not in existing_assumptions:
        defaults.append(("structural_system", "reinforced_concrete_frame", None,
            "Preliminary structural concept assumption; not engineering certification", ["structure", "geometry", "cost"]))
    for parameter, value, unit, reason, scope in defaults:
        assumption = AssumptionRecord(organization_id=project.organization_id, project_id=project.id,
            project_version_id=version.id, project_version=version.version, parameter=parameter,
            value_json={"value": value}, unit=unit, reason=reason, source="SYSTEM",
            status="proposed", impact_scope_json=scope, confidence=.5, created_by=user.id)
        session.add(assumption); await session.flush()
        await audit(session, project=project, version=version, actor=user.id, action="ASSUMPTION_CREATED",
            entity="assumption", entity_id=assumption.id, metadata={"parameter": parameter, "source": "SYSTEM"})
    version.revision_number += 1
    world = await persist_world_model(session, project, version, user.id, source="brief_ingestion")
    await audit(session, project=project, version=version, actor=user.id, action="BRIEF_SUBMITTED",
        entity="building_brief", entity_id=brief.id, metadata={"brief_revision": brief_revision})
    await session.commit()
    return {"brief": {"id": brief.id, "revision": brief.revision, "content_hash": brief.content_hash,
        "structured": brief.structured_json}, "requirements": [requirement_out(r) for r in created],
        "world_model_revision": {"id": world.id, "revision_number": world.revision, "model_hash": world.model_hash},
        "version_revision": version.revision_number}


@router.get("/projects/{project_id}/versions/{version_ref}/requirements")
async def list_requirements(project_id: str, version_ref: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    _, version = await resolve_project_version(session, project_id, version_ref, user.id)
    rows = (await session.scalars(select(RequirementRecord).where(
        RequirementRecord.project_version_id == version.id).order_by(RequirementRecord.created_at, RequirementRecord.id))).all()
    return {"version": version_out(version), "requirements": [requirement_out(row) for row in rows]}


@router.post("/projects/{project_id}/versions/{version_ref}/requirements/{requirement_id}/confirm")
async def decide_requirement(project_id: str, version_ref: str, requirement_id: str, body: RequirementDecision,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    await check_revision(version, body.expected_revision)
    if version.status != "DRAFT": raise error(409, "VERSION_CONFLICT", "Historical versions are immutable")
    row = await session.scalar(select(RequirementRecord).where(RequirementRecord.id == requirement_id,
        RequirementRecord.project_version_id == version.id))
    if row is None: raise error(404, "INVALID_REQUIREMENT", "Requirement not found")
    row.status = body.decision; row.confirmed_by = user.id; row.confirmed_at = datetime.now(timezone.utc)
    version.revision_number += 1
    world = await persist_world_model(session, project, version, user.id, source="requirement_decision")
    await audit(session, project=project, version=version, actor=user.id,
        action="REQUIREMENT_CONFIRMED" if body.decision == "CONFIRMED" else "REQUIREMENT_REJECTED",
        entity="requirement", entity_id=row.id, metadata={"parameter": row.parameter})
    await session.commit()
    return {"requirement": requirement_out(row), "version_revision": version.revision_number,
        "world_model_hash": world.model_hash}


@router.patch("/projects/{project_id}/versions/{version_ref}/requirements/{requirement_id}", status_code=201)
async def edit_requirement(project_id: str, version_ref: str, requirement_id: str, body: RequirementEdit,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    await check_revision(version, body.expected_revision)
    if version.status != "DRAFT": raise error(409, "VERSION_CONFLICT", "Historical versions are immutable")
    old = await session.scalar(select(RequirementRecord).where(RequirementRecord.id == requirement_id,
        RequirementRecord.project_version_id == version.id))
    if old is None: raise error(404, "INVALID_REQUIREMENT", "Requirement not found")
    old.status = "SUPERSEDED"
    row = RequirementRecord(organization_id=project.organization_id, project_id=project.id,
        project_version_id=version.id, source_text=body.reason, parameter=old.parameter, category=old.category,
        raw_value_json=body.value, extracted_value_json=body.value, normalized_value_json=body.value,
        value_type="integer" if isinstance(body.value, int) else "decimal" if isinstance(body.value, float) else "string",
        unit=body.unit or old.unit, source_type="HUMAN_REVIEW", source_reference=old.id,
        extraction_method="human_edit", confidence=1.0, status="CONFIRMED", confirmed_by=user.id,
        confirmed_at=datetime.now(timezone.utc), supersedes_id=old.id,
        provenance_json={"supersedes_requirement_id": old.id}, created_by=user.id)
    session.add(row); await session.flush(); version.revision_number += 1
    world = await persist_world_model(session, project, version, user.id, source="requirement_edit")
    await audit(session, project=project, version=version, actor=user.id, action="REQUIREMENT_CHANGED",
        entity="requirement", entity_id=row.id, metadata={"parameter": row.parameter, "supersedes_id": old.id})
    await session.commit()
    return {"requirement": requirement_out(row), "version_revision": version.revision_number,
        "world_model_hash": world.model_hash}


@router.get("/projects/{project_id}/versions/{version_ref}/assumptions")
async def list_version_assumptions(project_id: str, version_ref: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    _, version = await resolve_project_version(session, project_id, version_ref, user.id)
    rows = (await session.scalars(select(AssumptionRecord).where(
        AssumptionRecord.project_version_id == version.id).order_by(AssumptionRecord.created_at, AssumptionRecord.id))).all()
    return {"version": version_out(version), "assumptions": [assumption_out(row) for row in rows]}


@router.post("/projects/{project_id}/versions/{version_ref}/assumptions", status_code=201)
async def create_version_assumption(project_id: str, version_ref: str, body: AssumptionIn,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    await check_revision(version, body.expected_revision)
    if version.status != "DRAFT": raise error(409, "VERSION_CONFLICT", "Historical versions are immutable")
    row = AssumptionRecord(organization_id=project.organization_id, project_id=project.id,
        project_version_id=version.id, project_version=version.version, parameter=body.parameter,
        value_json={"value": body.value}, unit=body.unit, reason=body.reason, source=body.source,
        status="proposed", impact_scope_json=body.impact_scope, confidence=body.confidence, created_by=user.id)
    session.add(row); await session.flush(); version.revision_number += 1
    world = await persist_world_model(session, project, version, user.id, source="assumption_created")
    await audit(session, project=project, version=version, actor=user.id, action="ASSUMPTION_CREATED",
        entity="assumption", entity_id=row.id, metadata={"parameter": row.parameter, "source": row.source})
    await session.commit()
    return {"assumption": assumption_out(row), "version_revision": version.revision_number,
        "world_model_hash": world.model_hash}


@router.patch("/projects/{project_id}/versions/{version_ref}/assumptions/{assumption_id}")
async def patch_version_assumption(project_id: str, version_ref: str, assumption_id: str, body: AssumptionPatch,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    await check_revision(version, body.expected_revision)
    if version.status != "DRAFT": raise error(409, "VERSION_CONFLICT", "Historical versions are immutable")
    old = await session.scalar(select(AssumptionRecord).where(AssumptionRecord.id == assumption_id,
        AssumptionRecord.project_version_id == version.id))
    if old is None: raise error(404, "INVALID_ASSUMPTION", "Assumption not found")
    row = old
    action = "ASSUMPTION_ACCEPTED" if body.status == "accepted" else "ASSUMPTION_REJECTED"
    if body.value is not None:
        old.status = "superseded"
        row = AssumptionRecord(organization_id=project.organization_id, project_id=project.id,
            project_version_id=version.id, project_version=version.version, parameter=old.parameter,
            value_json={"value": body.value}, unit=old.unit, reason=body.reason or old.reason,
            source="HUMAN_REVIEW", status=body.status or "proposed", impact_scope_json=old.impact_scope_json,
            confidence=1.0, created_by=user.id, supersedes_id=old.id)
        session.add(row); await session.flush(); action = "ASSUMPTION_SUPERSEDED"
    elif body.status is not None: row.status = body.status
    else: raise error(422, "INVALID_ASSUMPTION", "Provide a status or replacement value")
    version.revision_number += 1
    world = await persist_world_model(session, project, version, user.id, source="assumption_mutation")
    await audit(session, project=project, version=version, actor=user.id, action=action,
        entity="assumption", entity_id=row.id, metadata={"parameter": row.parameter, "supersedes_id": row.supersedes_id})
    await session.commit()
    return {"assumption": assumption_out(row), "version_revision": version.revision_number,
        "world_model_hash": world.model_hash}


@router.get("/projects/{project_id}/versions/{version_ref}/world-model")
async def get_version_world_model(project_id: str, version_ref: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    _, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    return {"version": version_out(version), "world_model_revision": {"id": world.id,
        "revision_number": world.revision, "model_hash": world.model_hash, "source": world.source,
        "created_at": world.created_at}, "world_model": world.model_json}


@router.post("/projects/{project_id}/versions/{version_ref}/world-model")
async def commit_world_model(project_id: str, version_ref: str, body: WorldModelCommit,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    await check_revision(version, body.expected_revision)
    if version.status != "DRAFT": raise error(409, "VERSION_CONFLICT", "Historical versions are immutable")
    world = await persist_world_model(session, project, version, user.id, source="explicit_commit")
    contradictions = [item for item in world.model_json.get("consistency_issues", []) if item.get("code") == "CONTRADICTORY_REQUIREMENTS"]
    if contradictions:
        await session.rollback()
        raise error(409, "CONTRADICTORY_REQUIREMENTS", "Resolve contradictory requirements before commit", issues=contradictions)
    version.revision_number += 1
    if body.commit:
        version.status = "COMMITTED"
        await audit(session, project=project, version=version, actor=user.id, action="VERSION_COMMITTED",
            entity="project_version", entity_id=version.id, metadata={"model_hash": world.model_hash})
    await session.commit()
    return {"version": version_out(version), "world_model_revision": {"id": world.id,
        "revision_number": world.revision, "model_hash": world.model_hash}, "world_model": world.model_json}


@router.get("/projects/{project_id}/versions/{version_ref}/snapshot")
async def foundation_snapshot(project_id: str, version_ref: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    brief = await session.scalar(select(BuildingBriefRecord).where(
        BuildingBriefRecord.project_version_id == version.id).order_by(BuildingBriefRecord.revision.desc()))
    requirements = (await session.scalars(select(RequirementRecord).where(
        RequirementRecord.project_version_id == version.id).order_by(RequirementRecord.created_at, RequirementRecord.id))).all()
    assumptions = (await session.scalars(select(AssumptionRecord).where(
        AssumptionRecord.project_version_id == version.id).order_by(AssumptionRecord.created_at, AssumptionRecord.id))).all()
    return {"project": {"id": project.id, "organization_id": project.organization_id, "name": project.name,
        "description": project.description, "project_type": project.building_type, "location": project.location,
        "status": project.status, "current_version_id": project.current_version_id, "metadata": project.metadata_json},
        "version": version_out(version), "brief": None if brief is None else {"id": brief.id, "revision": brief.revision,
            "raw_text": brief.raw_text, "structured": brief.structured_json, "content_hash": brief.content_hash,
            "source_type": brief.source_type, "source_reference": brief.source_reference},
        "requirements": [requirement_out(row) for row in requirements],
        "assumptions": [assumption_out(row) for row in assumptions],
        "world_model_revision": {"id": world.id, "revision_number": world.revision, "model_hash": world.model_hash,
            "source": world.source, "created_at": world.created_at}, "world_model": world.model_json}


@router.get("/projects/{project_id}/audit-events")
async def list_audit_events(project_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project, _ = await resolve_project(session, project_id, user.id)
    rows = (await session.scalars(select(AuditEvent).where(AuditEvent.project_id == project.id).order_by(AuditEvent.created_at, AuditEvent.id))).all()
    return {"events": [{"id": row.id, "action": row.action, "actor_user_id": row.actor_user_id,
        "project_version_id": row.project_version_id, "entity": row.resource_type, "entity_id": row.resource_id,
        "metadata": row.metadata_json, "created_at": row.created_at} for row in rows]}
