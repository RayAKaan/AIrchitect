from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DesignAlternative, DesignGenerationRun, GeometryArtifact, Membership, ReviewRecord, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.design.engine import ENGINE, DesignGenerationError
from app.domains.design.evaluation import evaluate_alternatives
from app.domains.design.lineage import alternative_is_stale, current_design_input_lineage
from app.domains.foundation.service import audit, error, resolve_project_version, resolve_world_model
from .schemas import AlternativeApproval, AlternativeSelection

router=APIRouter(tags=["computational-design"])


def alternative_out(
    row: DesignAlternative,
    geometry: GeometryArtifact | None,
    current_hash: str,
    current_lineage: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    lineage = current_lineage or {}
    status = "STALE" if alternative_is_stale(row, current_hash, lineage) and row.status in {"VALID", "SELECTED"} else row.status
    return {"id":row.id,"project_id":row.project_id,"project_version_id":row.project_version_id,
        "world_model_revision_id":row.world_model_revision_id,"generation_run_id":row.generation_run_id,
        "name":row.name,"description":row.description,"strategy_id":row.strategy_id,"strategy_version":row.strategy_version,
        "status":status,"parameters":row.design_parameters_json,"metrics":row.key_metrics_json,
        "constraint_results":row.constraint_results_json,"reasoning":row.reasoning_json,
        "assumptions":row.assumptions_json,"unknowns":row.unknowns_json,"tradeoffs":row.tradeoffs_json,
        "design_engine_version":row.design_engine_version,"config_version":row.design_engine_config_version,
        "input_world_model_hash":row.input_world_model_hash,"design_hash":row.design_hash,
        "provenance":row.provenance_json,"geometry_available":geometry is not None,
        "geometry_hash":geometry.geometry_hash if geometry else None,"geometry_status":geometry.status if geometry else None,
        "selected_by":row.selected_by,"selected_at":row.selected_at,"selection_reason":row.selection_reason,
        "design_direction_approval":(row.provenance_json or {}).get("design_direction_approval"),
        "created_at":row.created_at,"updated_at":row.updated_at}


async def load_alt(session:AsyncSession,project_id:str,version_id:str,alternative_id:str,user:User,write:bool=False):
    project,version=await resolve_project_version(session,project_id,version_id,user.id,write=write)
    alt=await session.scalar(select(DesignAlternative).where(DesignAlternative.id==alternative_id,
        DesignAlternative.project_id==project.id,DesignAlternative.project_version_id==version.id))
    if alt is None:raise error(404,"ALTERNATIVE_NOT_FOUND","Design alternative not found")
    world=await resolve_world_model(session,version.id)
    return project,version,world,alt


@router.post("/projects/{project_id}/versions/{version_ref}/design/generate",status_code=201)
async def generate_design(project_id:str,version_ref:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    project,version=await resolve_project_version(session,project_id,version_ref,user.id,write=True)
    if version.status!="COMMITTED":raise error(409,"WORLD_MODEL_INVALID","Commit the canonical project version before design generation",version_status=version.status)
    world=await resolve_world_model(session,version.id)
    serious=[x for x in world.model_json.get("consistency_issues",[]) if x.get("code") in {"CONTRADICTORY_REQUIREMENTS","HEIGHT_FLOOR_INCONSISTENCY"}]
    if serious:raise error(409,"WORLD_MODEL_INVALID","Resolve World Model consistency issues before design generation",issues=serious)
    try:run=await ENGINE.generate(session,project,version,world,user)
    except DesignGenerationError as exc:raise error(409,exc.code,exc.message,**exc.context) from exc
    return {"generation_id":run.id,"status":run.status,"world_model_hash":run.world_model_hash,
        "engine_version":run.engine_version,"config_version":run.config_version,"progress":run.progress_json,
        "alternative_ids":run.generated_alternative_ids_json,"idempotent":bool(getattr(run,"_idempotent_reuse",False))}


@router.get("/projects/{project_id}/versions/{version_ref}/design/generations/{generation_id}")
async def generation_status(project_id:str,version_ref:str,generation_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    _,version=await resolve_project_version(session,project_id,version_ref,user.id)
    row=await session.scalar(select(DesignGenerationRun).where(DesignGenerationRun.id==generation_id,
        DesignGenerationRun.project_version_id==version.id))
    if row is None:raise error(404,"DESIGN_GENERATION_NOT_FOUND","Design generation run not found")
    return {"id":row.id,"status":row.status,"world_model_hash":row.world_model_hash,"engine_version":row.engine_version,
        "config_version":row.config_version,"progress":row.progress_json,"alternative_ids":row.generated_alternative_ids_json,
        "error":{"code":row.error_code,"message":row.error_message} if row.error_code else None,
        "requested_at":row.requested_at,"completed_at":row.completed_at}


@router.get("/projects/{project_id}/versions/{version_ref}/design/alternatives")
async def list_alternatives(project_id:str,version_ref:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    _,version=await resolve_project_version(session,project_id,version_ref,user.id)
    world=await resolve_world_model(session,version.id)
    rows=list((await session.scalars(select(DesignAlternative).where(DesignAlternative.project_version_id==version.id).order_by(DesignAlternative.created_at,DesignAlternative.id))).all())
    geometries=list((await session.scalars(select(GeometryArtifact).where(GeometryArtifact.project_version_id==version.id,GeometryArtifact.source=="CAD_BREP").order_by(GeometryArtifact.created_at.desc()))).all())
    by_alt={}
    for geometry_row in geometries:
        by_alt.setdefault(geometry_row.alternative_id,geometry_row)
    lineage = await current_design_input_lineage(session, version.id)
    return {"project_version_id": version.id, "world_model_hash": world.model_hash,
        "input_lineage": lineage,
        "alternatives": [
            alternative_out(row, by_alt.get(row.id), world.model_hash or "", lineage) for row in rows
        ]}


@router.get("/projects/{project_id}/versions/{version_ref}/design/alternatives/{alternative_id}")
async def get_alternative(project_id:str,version_ref:str,alternative_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    _,_,world,alt=await load_alt(session,project_id,version_ref,alternative_id,user)
    geometry=await session.scalar(select(GeometryArtifact).where(GeometryArtifact.alternative_id==alt.id,GeometryArtifact.project_version_id==alt.project_version_id,GeometryArtifact.source=="CAD_BREP").order_by(GeometryArtifact.created_at.desc()))
    return alternative_out(alt,geometry,world.model_hash or "")


@router.get("/projects/{project_id}/versions/{version_ref}/design/alternatives/{alternative_id}/geometry")
async def get_geometry(project_id:str,version_ref:str,alternative_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    _,_,world,alt=await load_alt(session,project_id,version_ref,alternative_id,user)
    geometry=await session.scalar(select(GeometryArtifact).where(GeometryArtifact.alternative_id==alt.id,
        GeometryArtifact.project_version_id==alt.project_version_id,GeometryArtifact.source=="CAD_BREP").order_by(GeometryArtifact.created_at.desc()))
    if geometry is None:raise error(409,"CAD_REQUIRED","No authoritative CAD geometry exists for this alternative. Generate a CAD/BIM model before viewing geometry or running engineering analysis.")
    status="STALE" if geometry.input_world_model_hash!=(world.model_hash or "") and geometry.status=="CURRENT" else geometry.status
    return {"id":geometry.id,"alternative_id":alt.id,"project_version_id":alt.project_version_id,
        "world_model_revision_id":geometry.world_model_revision_id,"status":status,"geometry_hash":geometry.geometry_hash,
        "input_world_model_hash":geometry.input_world_model_hash,"design_hash":geometry.design_hash,
        "engine_name":geometry.engine_name,"engine_version":geometry.engine_version,"provenance":geometry.provenance_json,
        "validation":geometry.payload_json.get("validation"),
        "created_at":geometry.created_at,"updated_at":geometry.updated_at}


@router.get("/projects/{project_id}/versions/{version_ref}/design/comparison")
async def design_comparison(project_id:str,version_ref:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    payload=await list_alternatives(project_id,version_ref,user,session)
    current_alternatives = [
        row for row in payload["alternatives"] if row["status"] in {"VALID", "SELECTED"}
    ]
    return {
        "project_version_id": payload["project_version_id"],
        "world_model_hash": payload["world_model_hash"],
        "input_lineage": payload["input_lineage"],
        "comparison_dimensions": [
            "strategy_id", "gross_floor_area_m2", "building_footprint_m2", "site_coverage_ratio",
            "floor_count", "building_height_m", "open_site_area_m2", "parking_count",
        ],
        "alternatives": evaluate_alternatives(payload["alternatives"]),
        "comparable": len(current_alternatives) > 1,
        "evaluation_method": "transparent_multi_criteria_pareto_v1",
        "notice": "Only alternatives with current matching source lineage are comparable. No weighted overall score or automatic optimal design is claimed.",
    }


@router.post("/projects/{project_id}/versions/{version_ref}/design/alternatives/{alternative_id}/select")
async def select_alternative(project_id:str,version_ref:str,alternative_id:str,body:AlternativeSelection,
    user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    project,version,world,alt=await load_alt(session,project_id,version_ref,alternative_id,user,write=True)
    current_lineage = await current_design_input_lineage(session, version.id)
    if alternative_is_stale(alt, world.model_hash or "", current_lineage) or alt.status == "STALE":
        raise error(
            409,
            "STALE_ARTIFACT",
            "A stale alternative cannot be selected; regenerate from the current World Model, program and envelope",
            current_world_model_hash=world.model_hash,
            current_input_lineage=current_lineage,
            alternative_input_lineage=(alt.provenance_json or {}).get("input_lineage", {}),
        )
    if alt.status not in {"VALID","SELECTED"}:raise error(409,"ALTERNATIVE_NOT_SELECTABLE","Only valid alternatives can be selected",alternative_status=alt.status)
    rows=list((await session.scalars(select(DesignAlternative).where(DesignAlternative.project_version_id==version.id).with_for_update())).all())
    for row in rows:
        if row.id!=alt.id and row.status=="SELECTED":
            row.status="VALID";row.selected_by=None;row.selected_at=None;row.selection_reason=None
    alt.status = "SELECTED"
    alt.selected_by = user.id
    alt.selected_at = datetime.now(timezone.utc)
    alt.selection_reason = body.reason
    alt.provenance_json = {
        **(alt.provenance_json or {}),
        "selection_input_lineage": current_lineage,
    }
    await audit(
        session, project=project, version=version, actor=user.id, action="ALTERNATIVE_SELECTED",
        entity="design_alternative", entity_id=alt.id,
        metadata={
            "reason": body.reason,
            "design_hash": alt.design_hash,
            "world_model_hash": world.model_hash,
            "input_lineage": current_lineage,
        },
    )
    await session.commit()
    return {
        "alternative_id": alt.id,
        "status": alt.status,
        "selected_by": alt.selected_by,
        "selected_at": alt.selected_at,
        "selection_reason": alt.selection_reason,
        "world_model_hash": world.model_hash,
        "input_lineage": current_lineage,
        "notice": "Selection records a human design direction; it is not approval or certification.",
    }



@router.post("/projects/{project_id}/versions/{version_ref}/design/alternatives/{alternative_id}/approve")
async def approve_alternative(
    project_id: str,
    version_ref: str,
    alternative_id: str,
    body: AlternativeApproval,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    project, version, world, alt = await load_alt(
        session, project_id, version_ref, alternative_id, user, write=True
    )
    if version.status != "COMMITTED":
        raise error(409, "WORLD_MODEL_INVALID", "Commit the canonical project version before approving a design direction")
    membership = await session.scalar(
        select(Membership).where(
            Membership.organization_id == project.organization_id,
            Membership.user_id == user.id,
        )
    )
    if membership is None or membership.role not in {"owner", "admin"}:
        raise error(403, "APPROVAL_ROLE_REQUIRED", "Only project owners or organization admins can approve a design direction")
    if alt.status != "SELECTED":
        raise error(409, "ALTERNATIVE_NOT_SELECTED", "Select the design direction before approving it", alternative_status=alt.status)

    current_lineage = await current_design_input_lineage(session, version.id)
    if alternative_is_stale(alt, world.model_hash or "", current_lineage):
        raise error(
            409,
            "STALE_ARTIFACT",
            "A stale design direction cannot be approved; regenerate and select an alternative from current inputs",
            current_world_model_hash=world.model_hash,
            current_input_lineage=current_lineage,
            alternative_input_lineage=(alt.provenance_json or {}).get("input_lineage", {}),
        )
    failures = [
        check for check in (alt.constraint_results_json or [])
        if isinstance(check, dict) and str(check.get("status", "")).upper() == "FAIL"
    ]
    if failures:
        raise error(
            409,
            "ALTERNATIVE_CONSTRAINTS_FAILED",
            "A design direction with failed constraints cannot be approved",
            failed_constraints=failures,
        )
    if not alt.design_hash:
        raise error(409, "DESIGN_HASH_REQUIRED", "A persisted design hash is required for approval")

    existing = await session.scalar(
        select(ReviewRecord)
        .where(
            ReviewRecord.artifact_id == alt.id,
            ReviewRecord.source_hash == alt.design_hash,
            ReviewRecord.decision == "APPROVED_FOR_DEVELOPMENT",
        )
        .order_by(ReviewRecord.reviewed_at.desc())
        .limit(1)
    )
    if existing is not None:
        return {
            "review_id": existing.id,
            "alternative_id": alt.id,
            "status": existing.decision,
            "reviewer_role": existing.reviewer_role,
            "reason": existing.rationale,
            "idempotent": True,
            "notice": "This records approval to continue design development only; it is not regulatory, code, engineering or construction approval.",
        }

    review = ReviewRecord(
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        artifact_versions_json=[{
            "artifact_version_id": alt.artifact_version_id,
            "design_hash": alt.design_hash,
            "world_model_hash": world.model_hash,
            "input_lineage": current_lineage,
        }],
        world_model_version=world.model_hash or "",
        status="REVIEWED",
        artifact_id=alt.id,
        artifact_version=str(alt.artifact_version_id or alt.design_engine_version),
        source_hash=alt.design_hash,
        reviewer_user_id=user.id,
        reviewer_role=membership.role,
        decision="APPROVED_FOR_DEVELOPMENT",
        rationale=body.reason,
        comments=body.comments,
    )
    session.add(review)
    await session.flush()
    approved_at = review.reviewed_at or datetime.now(timezone.utc)
    alt.provenance_json = {
        **(alt.provenance_json or {}),
        "design_direction_approval": {
            "review_id": review.id,
            "status": "APPROVED_FOR_DEVELOPMENT",
            "approved_by": user.id,
            "approved_at": approved_at.isoformat(),
            "reason": body.reason,
            "world_model_hash": world.model_hash,
            "input_lineage": current_lineage,
        },
    }
    await audit(
        session,
        project=project,
        version=version,
        actor=user.id,
        action="ALTERNATIVE_APPROVED_FOR_DEVELOPMENT",
        entity="design_alternative",
        entity_id=alt.id,
        metadata={
            "review_id": review.id,
            "design_hash": alt.design_hash,
            "world_model_hash": world.model_hash,
            "input_lineage": current_lineage,
            "reviewer_role": membership.role,
        },
    )
    await session.commit()
    return {
        "review_id": review.id,
        "alternative_id": alt.id,
        "status": "APPROVED_FOR_DEVELOPMENT",
        "reviewer_role": membership.role,
        "reason": body.reason,
        "approved_at": approved_at,
        "idempotent": False,
        "notice": "This records approval to continue design development only; it is not regulatory, code, engineering or construction approval.",
    }
