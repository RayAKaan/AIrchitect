from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import (CostEstimate,DesignAlternative,GeometryArtifact,Project,ProjectVersion,QuantityArtifact,RateEntry,RateSchedule,
 RegulatoryEvaluation,StructuralArtifact,User,ValidationRun)
from app.db.session import get_session
from app.dependencies import current_user,require_membership
from app.domains.foundation.service import audit,error,resolve_project_version,resolve_world_model
from .engines import EngineeringError
from .schemas import EngineeringCalculateRequest,RateScheduleCreate
from .service import calculate_all,resolve_sources,schedule_out,summary
router=APIRouter(tags=["phase3-engineering"])

@router.post("/engineering/rate-schedules",status_code=201)
async def create_rate_schedule(body:RateScheduleCreate,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
 await require_membership(body.organization_id,user,session,{"owner","admin","member"})
 if body.source_type=="VERIFIED_EXTERNAL":raise error(422,"RATE_SOURCE_NOT_VERIFIED","User-created schedules cannot claim VERIFIED_EXTERNAL status; use USER_PROVIDED or DEMO")
 row=RateSchedule(organization_id=body.organization_id,name=body.name,version=body.version,geography=body.jurisdiction,jurisdiction=body.jurisdiction,currency=body.currency,source=body.source_reference,source_type=body.source_type,source_reference=body.source_reference,source_date=body.effective_date,effective_date=body.effective_date,status="ACTIVE",is_demo=body.source_type=="DEMO",rates_json=[x.model_dump() for x in body.entries],created_by=user.id);session.add(row);await session.flush()
 for x in body.entries:session.add(RateEntry(rate_schedule_id=row.id,item_code=x.item_code,category=x.category,description=x.description,unit=x.unit,rate=x.rate,low_rate=x.low_rate,high_rate=x.high_rate,currency=body.currency,source_type=body.source_type,source_reference=x.source_reference,effective_date=x.effective_date,confidence=x.confidence,metadata_json={"quantity_code":x.quantity_code}))
 await session.commit();entries=list((await session.scalars(select(RateEntry).where(RateEntry.rate_schedule_id==row.id))).all());return schedule_out(row,entries)

@router.get("/engineering/rate-schedules")
async def list_rate_schedules(organization_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
 await require_membership(organization_id,user,session);rows=list((await session.scalars(select(RateSchedule).where(RateSchedule.organization_id==organization_id,RateSchedule.status=="ACTIVE").order_by(RateSchedule.created_at.desc()))).all());out=[]
 for row in rows:out.append(schedule_out(row,list((await session.scalars(select(RateEntry).where(RateEntry.rate_schedule_id==row.id))).all())))
 return out

@router.post("/projects/{project_id}/versions/{version_ref}/design/alternatives/{alternative_id}/engineering/calculate",status_code=201)
async def calculate_engineering(project_id:str,version_ref:str,alternative_id:str,body:EngineeringCalculateRequest,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
 project,version,world,alt,geom,gi=await resolve_sources(session,project_id,version_ref,alternative_id,user,write=True);ids=(project.id,version.id,alt.id,user.id)
 try:return await calculate_all(session,project,version,world,alt,geom,user,body.rate_schedule_id,gi=gi)
 except EngineeringError as exc:
  await session.rollback();pid,vid,aid,uid=ids;failed_project=await session.get(Project,pid);failed_version=await session.get(ProjectVersion,vid)
  action=("COST_CALCULATION_FAILED" if exc.code.startswith(("RATE_","COST_")) else "STRUCTURAL_CONCEPT_FAILED" if exc.code.startswith("STRUCTURAL_") else "REGULATORY_EVALUATION_FAILED" if exc.code.startswith("REGULATORY_") else "QUANTITY_CALCULATION_FAILED")
  if failed_project and failed_version:
   await audit(session,project=failed_project,version=failed_version,actor=uid,action=action,entity="design_alternative",entity_id=aid,metadata={"code":exc.code,"message":exc.message});await session.commit()
  raise error(409,exc.code,exc.message,**exc.context) from exc
 except Exception as exc:
  await session.rollback();pid,vid,aid,uid=ids;failed_project=await session.get(Project,pid);failed_version=await session.get(ProjectVersion,vid)
  if failed_project and failed_version:
   await audit(session,project=failed_project,version=failed_version,actor=uid,action="PHASE3_CALCULATION_FAILED",entity="design_alternative",entity_id=aid,metadata={"code":"ENGINEERING_CALCULATION_FAILED"});await session.commit()
  raise error(500,"ENGINEERING_CALCULATION_FAILED","Engineering calculation failed unexpectedly; retry or contact support") from exc

@router.get("/projects/{project_id}/versions/{version_ref}/design/alternatives/{alternative_id}/engineering")
async def get_engineering(project_id:str,version_ref:str,alternative_id:str,rate_schedule_id:str|None=None,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
 project,version,world,alt,geom,gi=await resolve_sources(session,project_id,version_ref,alternative_id,user)
 result=await summary(session,project,version,world,alt,geom,rate_schedule_id)
 if result["quantity"] is None:raise error(404,"ENGINEERING_ARTIFACTS_NOT_FOUND","Calculate engineering artifacts for this alternative first")
 if result["cost"] is None:result["cost_error"]={"code":"COST_UNAVAILABLE","message":"No matching cost estimate exists. Select an explicitly sourced rate schedule to calculate cost."}
 return result

@router.get("/projects/{project_id}/versions/{version_ref}/engineering/comparison")
async def engineering_comparison(project_id:str,version_ref:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
 _,version=await resolve_project_version(session,project_id,version_ref,user.id);await resolve_world_model(session,version.id)
 alts=list((await session.scalars(select(DesignAlternative).where(DesignAlternative.project_version_id==version.id).order_by(DesignAlternative.created_at))).all());rows=[]
 for a in alts:
  q=await session.scalar(select(QuantityArtifact).where(QuantityArtifact.design_alternative_id==a.id).order_by(QuantityArtifact.created_at.desc()));c=await session.scalar(select(CostEstimate).where(CostEstimate.design_alternative_id==a.id).order_by(CostEstimate.created_at.desc()));s=await session.scalar(select(StructuralArtifact).where(StructuralArtifact.design_alternative_id==a.id).order_by(StructuralArtifact.created_at.desc()));r=await session.scalar(select(RegulatoryEvaluation).where(RegulatoryEvaluation.design_alternative_id==a.id).order_by(RegulatoryEvaluation.created_at.desc()));v=await session.scalar(select(ValidationRun).where(ValidationRun.design_alternative_id==a.id).order_by(ValidationRun.created_at.desc()))
  rows.append({"alternative_id":a.id,"name":a.name,"strategy_id":a.strategy_id,"metrics":a.key_metrics_json,"quantity_status":q.status if q else "NOT_CALCULATED","quantity_hash":q.quantity_hash if q else None,"cost_status":c.status if c else "COST_UNAVAILABLE","cost_total":c.total_cost if c else None,"cost_currency":c.currency if c else None,"structural_system":s.payload_json.get("structural_system") if s else None,"structural_status":s.status if s else "NOT_CALCULATED","regulatory_status":r.payload_json.get("overall_status") if r else "NOT_CALCULATED","validation_status":v.payload_json.get("status") if v else "NOT_CALCULATED"})
 return {"project_version_id":version.id,"alternatives":rows,"notice":"Engineering comparison exposes trade-offs and does not identify an overall winner."}
