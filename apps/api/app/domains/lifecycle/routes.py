from __future__ import annotations

import json
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ArtifactDependency, ArtifactVersion, AssumptionRecord, AuditEvent, DeliverableRecord,
    Project, ProjectVersion, RateSchedule, RequirementRecord, ReviewRecord, User,
    WorkflowRecord, WorkflowTaskRecord, WorldModelRevision,
)
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from app.domains.requirements.service import analyze_brief
from .schemas import BriefSubmission, DemoRateScheduleCreate, PipelineRun, VersionChange
from .service import canonical_hash, model_from_brief, run_pipeline, stale_prior_version

router = APIRouter(tags=["canonical-lifecycle"])


async def project_access(project_id: str, user: User, session: AsyncSession, write: bool = False) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    await require_membership(project.organization_id, user, session, {"owner", "admin", "member"} if write else None)
    return project


async def version_access(project: Project, number: int, session: AsyncSession) -> ProjectVersion:
    version = await session.scalar(select(ProjectVersion).where(ProjectVersion.project_id == project.id, ProjectVersion.version == number))
    if version is None:
        raise HTTPException(404, "Project version not found")
    return version


@router.get("/legacy/projects/{project_id}/versions", deprecated=True)
async def list_versions(project_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await project_access(project_id, user, session)
    rows = (await session.scalars(select(ProjectVersion).where(ProjectVersion.project_id == project.id).order_by(ProjectVersion.version.desc()))).all()
    return [{"id": v.id, "version": v.version, "status": v.status, "change_summary": v.change_summary,
             "parent_version_id": v.parent_version_id, "created_at": v.created_at} for v in rows]


@router.post("/projects/{project_id}/brief", status_code=201)
async def submit_brief(project_id: str, body: BriefSubmission, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await project_access(project_id, user, session, True)
    raise HTTPException(410, {"error": {"code": "CANONICAL_VERSION_REQUIRED",
        "message": "Non-versioned brief submission is disabled; use /projects/{id}/versions/{version_id}/brief."}})
    version = await session.scalar(select(ProjectVersion).where(ProjectVersion.project_id == project.id, ProjectVersion.version == project.version))  # pragma: no cover
    if version is None:
        version = ProjectVersion(organization_id=project.organization_id, project_id=project.id, version=project.version,
            status="draft", change_summary="Initial brief", created_by=user.id)
        session.add(version); await session.flush()
    existing = await session.scalar(select(func.count(RequirementRecord.id)).where(RequirementRecord.project_version_id == version.id))
    if existing:
        raise HTTPException(409, "This immutable project version already has a brief; create a change version")
    extracted, missing, issues = analyze_brief(body.brief)
    values: dict[str, set[str]] = {}
    for req in extracted: values.setdefault(req.parameter, set()).add(str(req.value))
    for req in extracted:
        conflict = len(values[req.parameter]) > 1
        session.add(RequirementRecord(organization_id=project.organization_id, project_id=project.id,
            project_version_id=version.id, source_text=req.source_text, parameter=req.parameter,
            category=str(req.category), extracted_value_json=req.value, normalized_value_json=req.value,
            unit=req.unit, confidence=1.0, provenance_json={"source": "user_brief", "brief_hash": canonical_hash(body.brief)},
            status="contradictory" if conflict else "unconfirmed", contradiction_group=req.parameter if conflict else None,
            created_by=user.id))
    model, critical_unknowns = model_from_brief(body.brief)
    revision_number = (await session.scalar(select(func.max(WorldModelRevision.revision)).where(WorldModelRevision.project_id == project.id)) or 0) + 1
    world = WorldModelRevision(organization_id=project.organization_id, project_id=project.id, project_version_id=version.id,
        revision=revision_number, model_json=model, model_hash=canonical_hash(model), created_by=user.id)
    session.add(world)
    for key in critical_unknowns:
        session.add(AssumptionRecord(organization_id=project.organization_id, project_id=project.id,
            project_version_id=version.id, project_version=version.version, parameter=key, value_json={"value": None},
            reason="Required value was not present in the brief; no value was fabricated.", source="brief-gap",
            status="proposed", impact_scope_json=["world_model", "geometry", "quantities", "cost", "structure", "regulatory"],
            confidence=0.0, created_by=user.id))
    session.add(AuditEvent(organization_id=project.organization_id, actor_user_id=user.id, action="brief.persisted",
        resource_type="project_version", resource_id=version.id, metadata_json={"world_model_revision": revision_number}))
    await session.commit()
    return {"project_id": project.id, "project_version_id": version.id, "version": version.version,
        "world_model_revision_id": world.id, "world_model_revision": revision_number,
        "requirements_persisted": len(extracted), "missing_information": missing,
        "critical_unknowns": critical_unknowns, "issues": [i.model_dump() for i in issues]}


@router.get("/legacy/projects/{project_id}/versions/{number}/snapshot", deprecated=True)
async def snapshot(project_id: str, number: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await project_access(project_id, user, session)
    version = await version_access(project, number, session)
    world = await session.scalar(select(WorldModelRevision).where(WorldModelRevision.project_version_id == version.id).order_by(WorldModelRevision.revision.desc()))
    reqs = (await session.scalars(select(RequirementRecord).where(RequirementRecord.project_version_id == version.id))).all()
    assumptions = (await session.scalars(select(AssumptionRecord).where(AssumptionRecord.project_version_id == version.id))).all()
    artifacts = (await session.scalars(select(ArtifactVersion).where(ArtifactVersion.project_version_id == version.id).order_by(ArtifactVersion.created_at))).all()
    deps = (await session.scalars(select(ArtifactDependency).where(ArtifactDependency.artifact_version_id.in_([a.id for a in artifacts])))).all() if artifacts else []
    workflows = (await session.scalars(select(WorkflowRecord).where(WorkflowRecord.project_version_id == version.id))).all()
    return {"project": {"id": project.id, "name": project.name}, "version": {"id": version.id, "number": version.version, "status": version.status},
        "world_model": None if world is None else {"id": world.id, "revision": world.revision, "hash": world.model_hash, "model": world.model_json},
        "requirements": [{"id": r.id, "parameter": r.parameter, "value": r.normalized_value_json, "unit": r.unit, "status": r.status, "source_text": r.source_text} for r in reqs],
        "assumptions": [{"id": a.id, "parameter": a.parameter, "value": a.value_json, "status": a.status, "impact_scope": a.impact_scope_json} for a in assumptions],
        "artifacts": [{"id": a.id, "type": a.artifact_type, "artifact_version": a.version, "status": a.status,
            "alternative_id": a.alternative_id, "hash": a.output_hash, "payload": a.payload_json,
            "depends_on": [d.depends_on_artifact_version_id for d in deps if d.artifact_version_id == a.id]} for a in artifacts],
        "workflows": [{"id": w.id, "state": w.state, "type": w.workflow_type} for w in workflows]}


@router.post("/organizations/{organization_id}/rate-schedules/demo", status_code=201)
async def create_demo_schedule(organization_id: str, body: DemoRateScheduleCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await require_membership(organization_id, user, session, {"owner", "admin", "member"})
    row = RateSchedule(organization_id=organization_id, name=body.name, version="demo-v1", geography=body.geography,
        source="Seeded demo assumption — NOT authoritative Saudi market data", source_date=body.source_date,
        is_demo=True, rates_json=body.rates, created_by=user.id)
    session.add(row); await session.commit(); await session.refresh(row)
    return {"id": row.id, "name": row.name, "version": row.version, "source": row.source, "is_demo": row.is_demo, "rates": row.rates_json}


@router.post("/projects/{project_id}/versions/{number}/feasibility/run", status_code=202)
async def feasibility_run(project_id: str, number: int, body: PipelineRun, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await project_access(project_id, user, session, True)
    version = await version_access(project, number, session)
    schedule = await session.get(RateSchedule, body.rate_schedule_id) if body.rate_schedule_id else None
    if schedule is None or schedule.organization_id != project.organization_id:
        raise HTTPException(422, "A rate schedule owned by the project organization is required")
    try:
        workflow = await run_pipeline(session, project, version, user.id, body.idempotency_key, schedule)
    except ValueError as exc:
        await session.rollback(); raise HTTPException(409, str(exc)) from exc
    return {"workflow_id": workflow.id, "state": workflow.state, "project_version_id": version.id}


@router.get("/workflows/{workflow_id}/events")
async def workflow_detail(workflow_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    workflow = await session.get(WorkflowRecord, workflow_id)
    if workflow is None: raise HTTPException(404, "Workflow not found")
    await require_membership(workflow.organization_id, user, session)
    tasks = (await session.scalars(select(WorkflowTaskRecord).where(WorkflowTaskRecord.workflow_id == workflow.id).order_by(WorkflowTaskRecord.id))).all()
    return {"id": workflow.id, "state": workflow.state, "tasks": [{"id": t.id, "key": t.key, "state": t.state,
        "attempts": t.attempts, "result": t.result_json, "error": t.error} for t in tasks]}


@router.post("/projects/{project_id}/versions/{number}/changes", status_code=201)
async def create_change(project_id: str, number: int, body: VersionChange, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await project_access(project_id, user, session, True)
    raise HTTPException(410, {"error": {"code": "CANONICAL_VERSION_REQUIRED",
        "message": "Legacy change mutation is disabled; use POST /projects/{id}/versions with optimistic concurrency."}})
    parent = await version_access(project, number, session)  # pragma: no cover
    if number != project.version: raise HTTPException(409, "Changes can only branch from the current project version")
    old_world = await session.scalar(select(WorldModelRevision).where(WorldModelRevision.project_version_id == parent.id).order_by(WorldModelRevision.revision.desc()))
    if old_world is None: raise HTTPException(409, "Current version has no World Model")
    allowed = {"floor_count", "floor_to_floor_m", "footprint_width_m", "footprint_depth_m", "target_gfa_m2"}
    unknown = set(body.changes) - allowed
    if unknown: raise HTTPException(422, f"Unsupported World Model changes: {sorted(unknown)}")
    model = json.loads(json.dumps(old_world.model_json))
    model.setdefault("building", {}).update(body.changes)
    model["unknowns"] = [x for x in model.get("unknowns", []) if x not in body.changes]
    model["provenance"] = {"source": "version_change", "parent_world_model_revision_id": old_world.id, "actor": user.id}
    new_number = project.version + 1
    version = ProjectVersion(organization_id=project.organization_id, project_id=project.id, version=new_number,
        status="draft", change_summary=body.summary, parent_version_id=parent.id, created_by=user.id)
    session.add(version); await session.flush()
    revision_number = (await session.scalar(select(func.max(WorldModelRevision.revision)).where(WorldModelRevision.project_id == project.id)) or 0) + 1
    world = WorldModelRevision(organization_id=project.organization_id, project_id=project.id, project_version_id=version.id,
        revision=revision_number, model_json=model, model_hash=canonical_hash(model), created_by=user.id)
    session.add(world)
    for key, value in body.changes.items():
        session.add(RequirementRecord(organization_id=project.organization_id, project_id=project.id, project_version_id=version.id,
            source_text=body.summary, parameter=key, category="change", extracted_value_json=value, normalized_value_json=value,
            unit="m" if key.endswith("_m") else None, confidence=1.0, provenance_json={"source": "user_change", "parent_version_id": parent.id},
            status="confirmed", created_by=user.id))
    stale_ids = await stale_prior_version(session, parent)
    project.version = new_number
    session.add(AuditEvent(organization_id=project.organization_id, actor_user_id=user.id, action="project.version_created",
        resource_type="project_version", resource_id=version.id, metadata_json={"changed_fields": sorted(body.changes), "stale_artifact_ids": stale_ids}))
    await session.commit()
    return {"project_version_id": version.id, "version": new_number, "world_model_revision_id": world.id,
        "stale_artifact_ids": stale_ids, "rerun_plan": ["geometry", "quantity", "cost", "structural", "regulatory", "validation", "deliverable"]}


@router.post("/projects/{project_id}/versions/{number}/review")
async def review_version(project_id: str, number: int, decision: str, rationale: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await project_access(project_id, user, session, True)
    membership = await require_membership(project.organization_id, user, session, {"owner", "admin"})
    if decision not in {"approved_for_feasibility", "changes_requested", "rejected"}: raise HTTPException(422, "Invalid review decision")
    version = await version_access(project, number, session)
    deliverable = await session.scalar(select(DeliverableRecord).where(DeliverableRecord.project_version_id == version.id).order_by(DeliverableRecord.created_at.desc()))
    if deliverable is None or deliverable.status == "stale": raise HTTPException(409, "No current deliverable is available for review")
    row = ReviewRecord(organization_id=project.organization_id, project_id=project.id, project_version_id=version.id,
        artifact_id=deliverable.artifact_id, artifact_version=deliverable.artifact_version, source_hash=deliverable.source_hash,
        reviewer_user_id=user.id, reviewer_role=membership.role, decision=decision, rationale=rationale)
    session.add(row)
    deliverable.status = "reviewed" if decision == "approved_for_feasibility" else "changes_requested"
    version.status = deliverable.status
    await session.commit()
    return {"review_id": row.id, "decision": decision, "deliverable_id": deliverable.id, "artifact_hash": deliverable.source_hash}


@router.get("/projects/{project_id}/versions/{number}/deliverables/latest")
async def latest_deliverable(project_id: str, number: int, format: str = "json", user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await project_access(project_id, user, session)
    version = await version_access(project, number, session)
    row = await session.scalar(select(DeliverableRecord).where(DeliverableRecord.project_version_id == version.id).order_by(DeliverableRecord.created_at.desc()))
    if row is None: raise HTTPException(404, "Deliverable not found")
    if format == "json": return {"id": row.id, "status": row.status, "source_hash": row.source_hash, "package": row.payload_json}
    if format != "pdf": raise HTTPException(422, "format must be json or pdf")
    buf = BytesIO(); pdf = canvas.Canvas(buf, pagesize=A4); width, height = A4; y = height - 48
    for line in ["PRELIMINARY BUILDING FEASIBILITY PACKAGE", f"Project: {project.name}", f"Project version: {number}",
                 f"Package hash: {row.source_hash}", f"Review status: {row.status}", "",
                 "NOT ENGINEERING CERTIFICATION OR REGULATORY APPROVAL", ""] + json.dumps(row.payload_json, indent=2).splitlines():
        if y < 48: pdf.showPage(); y = height - 48
        pdf.drawString(42, y, line[:112]); y -= 12
    pdf.save()
    return Response(buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="feasibility-v{number}.pdf"', "X-Package-Hash": row.source_hash})
