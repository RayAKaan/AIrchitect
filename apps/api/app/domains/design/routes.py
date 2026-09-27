from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DesignAlternative, DesignGenerationRun, GeometryArtifact, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.design.engine import ENGINE, DesignGenerationError
from app.domains.foundation.service import audit, error, resolve_project_version, resolve_world_model
from .schemas import AlternativeSelection

router=APIRouter(tags=["computational-design"])


def alternative_out(row:DesignAlternative,geometry:GeometryArtifact|None,current_hash:str)->dict[str,Any]:
    status="STALE" if row.input_world_model_hash!=current_hash and row.status in {"VALID","SELECTED"} else row.status
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
    geometries=list((await session.scalars(select(GeometryArtifact).where(GeometryArtifact.project_version_id==version.id))).all())
    by_alt={g.alternative_id:g for g in geometries}
    return {"project_version_id":version.id,"world_model_hash":world.model_hash,
        "alternatives":[alternative_out(row,by_alt.get(row.id),world.model_hash or "") for row in rows]}


@router.get("/projects/{project_id}/versions/{version_ref}/design/alternatives/{alternative_id}")
async def get_alternative(project_id:str,version_ref:str,alternative_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    _,_,world,alt=await load_alt(session,project_id,version_ref,alternative_id,user)
    geometry=await session.scalar(select(GeometryArtifact).where(GeometryArtifact.alternative_id==alt.id))
    return alternative_out(alt,geometry,world.model_hash or "")


@router.get("/projects/{project_id}/versions/{version_ref}/design/alternatives/{alternative_id}/geometry")
async def get_geometry(project_id:str,version_ref:str,alternative_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    _,_,world,alt=await load_alt(session,project_id,version_ref,alternative_id,user)
    geometry=await session.scalar(select(GeometryArtifact).where(GeometryArtifact.alternative_id==alt.id,
        GeometryArtifact.project_version_id==alt.project_version_id))
    if geometry is None:raise error(404,"GEOMETRY_NOT_FOUND","Geometry artifact not found")
    status="STALE" if geometry.input_world_model_hash!=(world.model_hash or "") and geometry.status=="CURRENT" else geometry.status
    return {"id":geometry.id,"alternative_id":alt.id,"project_version_id":alt.project_version_id,
        "world_model_revision_id":geometry.world_model_revision_id,"status":status,"geometry_hash":geometry.geometry_hash,
        "input_world_model_hash":geometry.input_world_model_hash,"design_hash":geometry.design_hash,
        "engine_name":geometry.engine_name,"engine_version":geometry.engine_version,"provenance":geometry.provenance_json,
        "geometry_ir":geometry.payload_json.get("geometry_ir"),"validation":geometry.payload_json.get("validation"),
        "created_at":geometry.created_at,"updated_at":geometry.updated_at}


@router.get("/projects/{project_id}/versions/{version_ref}/design/comparison")
async def design_comparison(project_id:str,version_ref:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    payload=await list_alternatives(project_id,version_ref,user,session)
    return {"project_version_id":payload["project_version_id"],"world_model_hash":payload["world_model_hash"],
        "comparison_dimensions":["strategy_id","gross_floor_area_m2","building_footprint_m2","site_coverage_ratio",
            "floor_count","building_height_m","open_site_area_m2","parking_count"],
        "alternatives":payload["alternatives"],"notice":"No single optimal design is claimed; compare explicit trade-offs."}


@router.post("/projects/{project_id}/versions/{version_ref}/design/alternatives/{alternative_id}/select")
async def select_alternative(project_id:str,version_ref:str,alternative_id:str,body:AlternativeSelection,
    user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    project,version,world,alt=await load_alt(session,project_id,version_ref,alternative_id,user,write=True)
    if alt.input_world_model_hash!=(world.model_hash or "") or alt.status=="STALE":
        raise error(409,"STALE_ARTIFACT","A stale alternative cannot be selected; regenerate from the current World Model")
    if alt.status not in {"VALID","SELECTED"}:raise error(409,"ALTERNATIVE_NOT_SELECTABLE","Only valid alternatives can be selected",alternative_status=alt.status)
    rows=list((await session.scalars(select(DesignAlternative).where(DesignAlternative.project_version_id==version.id).with_for_update())).all())
    for row in rows:
        if row.id!=alt.id and row.status=="SELECTED":
            row.status="VALID";row.selected_by=None;row.selected_at=None;row.selection_reason=None
    alt.status="SELECTED";alt.selected_by=user.id;alt.selected_at=datetime.now(timezone.utc);alt.selection_reason=body.reason
    await audit(session,project=project,version=version,actor=user.id,action="ALTERNATIVE_SELECTED",
        entity="design_alternative",entity_id=alt.id,metadata={"reason":body.reason,"design_hash":alt.design_hash})
    await session.commit()
    return {"alternative_id":alt.id,"status":alt.status,"selected_by":alt.selected_by,"selected_at":alt.selected_at,
        "selection_reason":alt.selection_reason,"notice":"Selection records a human design direction; it is not approval or certification."}
