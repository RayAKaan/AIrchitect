from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssumptionRecord, AuditEvent, BuildingBriefRecord, Membership, Project, ProjectVersion,
    RequirementRecord, User, WorldModelRevision,
)
from app.domains.lifecycle.service import canonical_hash
from app.domains.world_model.model import (
    Building, BuildingWorldModel, Level, Location, Parking, Quantity, Site, StructuralGrid,
    ValueProvenance,
)

ACTIVE_REQUIREMENT_STATES = {"EXTRACTED", "CONFIRMED", "ASSUMED", "CONTRADICTORY", "unconfirmed", "confirmed", "contradictory"}
ACTIVE_ASSUMPTION_STATES = {"proposed", "accepted", "PROPOSED", "ACCEPTED"}


def error(status: int, code: str, message: str, **context: Any) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, "context": context}})


async def resolve_project(session: AsyncSession, project_id: str, user_id: str, *, write: bool = False) -> tuple[Project, Membership]:
    row = await session.execute(select(Project, Membership).join(Membership,
        (Membership.organization_id == Project.organization_id) & (Membership.user_id == user_id)).where(Project.id == project_id))
    found = row.first()
    if found is None:
        # Deliberately do not reveal whether a cross-tenant project exists.
        raise error(404, "PROJECT_NOT_FOUND", "Project not found")
    project, membership = found
    if write and membership.role not in {"owner", "admin", "member"}:
        raise error(403, "FORBIDDEN", "The current role cannot modify this project")
    return project, membership


async def resolve_project_version(session: AsyncSession, project_id: str, version_ref: str | int,
                                  user_id: str, *, write: bool = False) -> tuple[Project, ProjectVersion]:
    project, _ = await resolve_project(session, project_id, user_id, write=write)
    condition = ProjectVersion.id == str(version_ref)
    if str(version_ref).isdigit():
        condition = (ProjectVersion.version == int(str(version_ref))) | condition
    version = await session.scalar(select(ProjectVersion).where(ProjectVersion.project_id == project.id, condition))
    if version is None:
        raise error(404, "VERSION_NOT_FOUND", "Project version not found")
    return project, version


async def resolve_world_model(session: AsyncSession, project_version_id: str) -> WorldModelRevision:
    world = await session.scalar(select(WorldModelRevision).where(
        WorldModelRevision.project_version_id == project_version_id).order_by(WorldModelRevision.revision.desc()).limit(1))
    if world is None:
        raise error(409, "WORLD_MODEL_NOT_READY", "The project version has no canonical World Model")
    expected = canonical_hash(world.model_json)
    if world.model_hash != expected:
        raise error(409, "INVALID_WORLD_MODEL", "Stored World Model hash verification failed")
    return world


async def audit(session: AsyncSession, *, project: Project, version: ProjectVersion | None, actor: str,
                action: str, entity: str, entity_id: str, metadata: dict[str, Any] | None = None) -> None:
    session.add(AuditEvent(organization_id=project.organization_id, project_id=project.id,
        project_version_id=version.id if version else None, actor_user_id=actor, action=action,
        resource_type=entity, resource_id=entity_id, metadata_json=metadata or {}))


def _value(records: list[RequirementRecord], parameter: str, issues: list[dict[str, Any]]):
    matches = [r for r in records if r.parameter == parameter and r.status in ACTIVE_REQUIREMENT_STATES]
    distinct = {json.dumps(r.normalized_value_json, sort_keys=True) for r in matches}
    if len(distinct) > 1:
        issues.append({"code": "CONTRADICTORY_REQUIREMENTS", "parameter": parameter,
            "requirement_ids": [r.id for r in matches]})
        return None, None
    row = matches[-1] if matches else None
    return (row.normalized_value_json, row) if row else (None, None)


def _assumption_value(records: list[AssumptionRecord], parameter: str):
    row = next((r for r in reversed(records) if r.parameter == parameter and r.status in ACTIVE_ASSUMPTION_STATES), None)
    if row is None:
        return None, None
    value = row.value_json.get("value") if isinstance(row.value_json, dict) else row.value_json
    return value, row


def build_world_model(project: Project, version: ProjectVersion, requirements: list[RequirementRecord],
                      assumptions: list[AssumptionRecord]) -> BuildingWorldModel:
    issues: list[dict[str, Any]] = []
    provenance: dict[str, ValueProvenance] = {}

    def resolve(parameter: str):
        value, req = _value(requirements, parameter, issues)
        if req is not None:
            provenance[parameter] = ValueProvenance(source_type="USER_BRIEF", source_id=req.id,
                confirmed=req.status in {"CONFIRMED", "confirmed"})
            return value
        value, assumption = _assumption_value(assumptions, parameter)
        if assumption is not None:
            provenance[parameter] = ValueProvenance(source_type="SYSTEM_ASSUMPTION", source_id=assumption.id,
                confirmed=assumption.status.lower() == "accepted")
        return value

    site_area, city, use = resolve("site_area"), resolve("city"), resolve("building_use")
    floors, f2f, height = resolve("floor_count"), resolve("floor_to_floor_height"), resolve("building_height")
    gfa, parking_arrangement, parking_spaces = resolve("target_gfa"), resolve("parking_arrangement"), resolve("parking_spaces")
    structural_system = resolve("structural_system")
    floor_count = int(floors) if floors is not None else None
    f2f_q = Quantity(value=float(f2f), unit="m") if f2f is not None else None
    height_q = Quantity(value=float(height), unit="m") if height is not None else None
    if floor_count is not None and f2f_q is not None:
        derived_height = floor_count * f2f_q.value
        if height_q is None:
            height_q = Quantity(value=derived_height, unit="m")
            provenance["building_height"] = ValueProvenance(source_type="DERIVED", source_id=version.id, confirmed=False)
        elif abs(height_q.value - derived_height) > .5:
            issues.append({"code": "HEIGHT_FLOOR_INCONSISTENCY", "explicit_height_m": height_q.value,
                "derived_height_m": derived_height, "floor_count": floor_count, "floor_to_floor_m": f2f_q.value})
    level_area = float(gfa) / floor_count if gfa is not None and floor_count else None
    levels = [Level(level_number=index + 1, name=f"Level {index + 1}",
        elevation=Quantity(value=index * f2f_q.value, unit="m") if f2f_q else None,
        floor_to_floor_height=f2f_q, area=Quantity(value=level_area, unit="m2") if level_area is not None else None)
        for index in range(floor_count or 0)]
    required = {"site.area": site_area, "building.use": use, "building.floor_count": floor_count,
        "building.target_gfa": gfa, "building.floor_to_floor_height": f2f, "parking.arrangement": parking_arrangement}
    unknowns = sorted(key for key, value in required.items() if value is None)
    return BuildingWorldModel(project_id=project.id, project_version_id=version.id,
        site=Site(location=Location(city=city), area=Quantity(value=float(site_area), unit="m2") if site_area is not None else None),
        building=Building(use=use, floor_count=floor_count, floor_to_floor_height=f2f_q, height=height_q,
            target_gfa=Quantity(value=float(gfa), unit="m2") if gfa is not None else None),
        levels=levels, parking=Parking(arrangement=parking_arrangement,
            spaces=Quantity(value=float(parking_spaces), unit="count") if parking_spaces is not None else None),
        structural_grid=StructuralGrid(system=structural_system), requirement_ids=[r.id for r in requirements],
        assumption_ids=[a.id for a in assumptions], provenance=provenance, unknowns=unknowns,
        consistency_issues=issues)


async def persist_world_model(session: AsyncSession, project: Project, version: ProjectVersion, actor: str,
                              *, source: str = "requirements_and_assumptions") -> WorldModelRevision:
    requirements = list((await session.scalars(select(RequirementRecord).where(
        RequirementRecord.project_version_id == version.id).order_by(RequirementRecord.created_at, RequirementRecord.id))).all())
    assumptions = list((await session.scalars(select(AssumptionRecord).where(
        AssumptionRecord.project_version_id == version.id).order_by(AssumptionRecord.created_at, AssumptionRecord.id))).all())
    model = build_world_model(project, version, requirements, assumptions)
    payload = model.model_dump(mode="json", exclude_none=False)
    latest = await session.scalar(select(func.max(WorldModelRevision.revision)).where(WorldModelRevision.project_id == project.id)) or 0
    row = WorldModelRevision(organization_id=project.organization_id, project_id=project.id,
        project_version_id=version.id, revision=latest + 1, model_json=payload, model_hash=canonical_hash(payload),
        source=source, metadata_json={"version_revision": version.revision_number}, created_by=actor)
    session.add(row); await session.flush()
    await audit(session, project=project, version=version, actor=actor, action="WORLD_MODEL_REVISED",
        entity="world_model_revision", entity_id=row.id, metadata={"revision": row.revision, "model_hash": row.model_hash})
    return row


async def create_initial_state(session: AsyncSession, project: Project, actor: str) -> tuple[ProjectVersion, WorldModelRevision]:
    version = ProjectVersion(organization_id=project.organization_id, project_id=project.id, version=1,
        status="DRAFT", revision_number=1, change_summary="Initial version", source="project_creation",
        metadata_json={}, created_by=actor)
    session.add(version); await session.flush()
    project.current_version_id = version.id; project.version = 1
    world = await persist_world_model(session, project, version, actor, source="project_creation")
    await audit(session, project=project, version=version, actor=actor, action="VERSION_CREATED",
        entity="project_version", entity_id=version.id, metadata={"version_number": 1})
    return version, world


async def create_next_version(session: AsyncSession, project_id: str, user: User, *, expected_current_version_id: str,
                              expected_revision: int, change_summary: str, changes: dict[str, Any],
                              idempotency_key: str) -> tuple[ProjectVersion, WorldModelRevision, bool]:
    project, _ = await resolve_project(session, project_id, user.id, write=True)
    project = await session.scalar(select(Project).where(Project.id == project.id).with_for_update())
    assert project is not None
    existing = await session.scalar(select(ProjectVersion).where(ProjectVersion.project_id == project.id,
        ProjectVersion.idempotency_key == idempotency_key))
    if existing:
        return existing, await resolve_world_model(session, existing.id), False
    parent = await session.get(ProjectVersion, project.current_version_id)
    if parent is None or parent.id != expected_current_version_id or parent.revision_number != expected_revision:
        raise error(409, "VERSION_CONFLICT", "The project version changed since it was read",
            current_version_id=project.current_version_id)
    next_number = (await session.scalar(select(func.max(ProjectVersion.version)).where(ProjectVersion.project_id == project.id)) or 0) + 1
    version = ProjectVersion(organization_id=project.organization_id, project_id=project.id, version=next_number,
        status="DRAFT", revision_number=1, parent_version_id=parent.id, change_summary=change_summary,
        source="user_change", metadata_json={"changed_parameters": sorted(changes)}, idempotency_key=idempotency_key,
        created_by=user.id)
    session.add(version); await session.flush()
    brief = await session.scalar(select(BuildingBriefRecord).where(BuildingBriefRecord.project_version_id == parent.id).order_by(BuildingBriefRecord.revision.desc()))
    if brief:
        session.add(BuildingBriefRecord(organization_id=project.organization_id, project_id=project.id,
            project_version_id=version.id, revision=1, raw_text=brief.raw_text, structured_json=brief.structured_json,
            source_type="VERSION_CLONE", source_reference=brief.id, content_hash=brief.content_hash, created_by=user.id))
    parent_requirements = list((await session.scalars(select(RequirementRecord).where(RequirementRecord.project_version_id == parent.id))).all())
    clones: dict[str, RequirementRecord] = {}
    for old in parent_requirements:
        clone = RequirementRecord(organization_id=project.organization_id, project_id=project.id,
            project_version_id=version.id, source_text=old.source_text, parameter=old.parameter, category=old.category,
            raw_value_json=old.raw_value_json, extracted_value_json=old.extracted_value_json,
            normalized_value_json=old.normalized_value_json, value_type=old.value_type, unit=old.unit,
            source_type="VERSION_CLONE", source_reference=old.id, extraction_method=old.extraction_method,
            confidence=old.confidence, status=old.status, provenance_json={"cloned_from_requirement_id": old.id},
            created_by=user.id)
        session.add(clone); await session.flush(); clones[old.parameter] = clone
    parent_assumptions = list((await session.scalars(select(AssumptionRecord).where(AssumptionRecord.project_version_id == parent.id))).all())
    for old in parent_assumptions:
        session.add(AssumptionRecord(organization_id=project.organization_id, project_id=project.id,
            project_version_id=version.id, project_version=next_number, parameter=old.parameter,
            value_json=old.value_json, unit=old.unit, reason=old.reason, source="version_clone",
            status=old.status, impact_scope_json=old.impact_scope_json, confidence=old.confidence,
            created_by=user.id, supersedes_id=None))
    unit_map = {"floor_count": "count", "target_gfa": "m2", "site_area": "m2",
                "floor_to_floor_height": "m", "building_height": "m", "parking_spaces": "count"}
    category_map = {"floor_count": "floor", "target_gfa": "area", "site_area": "site",
        "floor_to_floor_height": "height", "building_height": "height", "parking_spaces": "parking"}
    for parameter, value in changes.items():
        old = clones.get(parameter)
        if old: old.status = "SUPERSEDED"
        row = RequirementRecord(organization_id=project.organization_id, project_id=project.id,
            project_version_id=version.id, source_text=change_summary, parameter=parameter,
            category=category_map.get(parameter, "other"), raw_value_json=value, extracted_value_json=value,
            normalized_value_json=value, value_type="integer" if isinstance(value, int) else "decimal" if isinstance(value, float) else "string",
            unit=unit_map.get(parameter), source_type="HUMAN_REVIEW", source_reference=parent.id,
            extraction_method="explicit_version_change", confidence=1.0, confirmed_by=user.id,
            confirmed_at=datetime.now(timezone.utc), status="CONFIRMED", supersedes_id=old.id if old else None,
            provenance_json={"parent_version_id": parent.id}, created_by=user.id)
        session.add(row); await session.flush()
        await audit(session, project=project, version=version, actor=user.id, action="REQUIREMENT_CHANGED",
            entity="requirement", entity_id=row.id, metadata={"parameter": parameter, "old_requirement_id": old.id if old else None})
    await session.flush()
    world = await persist_world_model(session, project, version, user.id, source="version_change")
    parent.status = "SUPERSEDED"; project.current_version_id = version.id; project.version = next_number
    await audit(session, project=project, version=version, actor=user.id, action="VERSION_CREATED",
        entity="project_version", entity_id=version.id, metadata={"version_number": next_number, "parent_version_id": parent.id})
    return version, world, True
