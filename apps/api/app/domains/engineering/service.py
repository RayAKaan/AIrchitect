from __future__ import annotations
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import (ArtifactVersion,CostEstimate,DesignAlternative,GeometryArtifact,Project,ProjectVersion,
 QuantityArtifact,RateEntry,RateSchedule,RegulatoryEvaluation,RegulatoryResult,StructuralArtifact,User,
 ValidationCheck,ValidationRun,WorldModelRevision)
from app.domains.foundation.service import audit,error,resolve_project_version,resolve_world_model
from app.domains.lifecycle.service import new_artifact
from .config import DEFAULT_CONFIG
from .engines import (CostEngine,EngineeringError,EngineeringValidationEngine,QuantityEngine,RegulatoryEngine,
 StructuralConceptEngine,schedule_hash)
logger=logging.getLogger("engineering")
QENGINE=QuantityEngine();CENGINE=CostEngine();SENGINE=StructuralConceptEngine();RENGINE=RegulatoryEngine();VENGINE=EngineeringValidationEngine()

async def resolve_sources(session:AsyncSession,project_id:str,version_ref:str,alternative_id:str,user:User,write=False):
 project,version=await resolve_project_version(session,project_id,version_ref,user.id,write=write);world=await resolve_world_model(session,version.id)
 alt=await session.scalar(select(DesignAlternative).where(DesignAlternative.id==alternative_id,DesignAlternative.project_id==project.id,DesignAlternative.project_version_id==version.id))
 if alt is None:raise error(404,"ALTERNATIVE_NOT_FOUND","Design alternative not found")
 if alt.status=="STALE" or alt.input_world_model_hash!=(world.model_hash or ""):raise error(409,"STALE_ARTIFACT","Regenerate the design alternative from the current World Model")
 if alt.status not in {"VALID","SELECTED"}:raise error(409,"DEPENDENCY_INVALID","Alternative is not valid for engineering calculation",alternative_status=alt.status)
 geom=await session.scalar(select(GeometryArtifact).where(GeometryArtifact.alternative_id==alt.id,GeometryArtifact.project_version_id==version.id))
 if geom is None:raise error(409,"QUANTITY_SOURCE_INVALID","The alternative has no persisted geometry artifact")
 if geom.status!="CURRENT":raise error(409,"STALE_ARTIFACT","Geometry artifact is not current",geometry_status=geom.status)
 if geom.input_world_model_hash!=(world.model_hash or "") or geom.design_hash!=(alt.design_hash or ""):raise error(409,"STALE_ARTIFACT","Geometry dependencies do not match the current alternative")
 if not geom.payload_json.get("validation",{}).get("valid"):raise error(409,"QUANTITY_SOURCE_INVALID","Persisted geometry is not validated")
 return project,version,world,alt,geom

def alt_input(world,alt):return {"world_hash":world.model_hash or "","design_hash":alt.design_hash or "","metrics":alt.key_metrics_json,"parameters":alt.design_parameters_json}
def geom_input(geom):return {"id":geom.id,"geometry_hash":geom.geometry_hash,"geometry_ir":geom.payload_json["geometry_ir"],"validation":geom.payload_json.get("validation",{})}

def schedule_out(row:RateSchedule,entries:list[RateEntry])->dict:
 return {"id":row.id,"organization_id":row.organization_id,"name":row.name,"version":row.version,"jurisdiction":row.jurisdiction,"currency":row.currency,"source":row.source,"source_type":row.source_type,"source_reference":row.source_reference,"effective_date":row.effective_date,"status":row.status,"is_demo":row.is_demo,"entries":[{"id":x.id,"item_code":x.item_code,"category":x.category,"description":x.description,"quantity_code":x.metadata_json.get("quantity_code"),"unit":x.unit,"rate":x.rate,"low_rate":x.low_rate,"high_rate":x.high_rate,"currency":x.currency,"source_type":x.source_type,"source_reference":x.source_reference,"effective_date":x.effective_date,"confidence":x.confidence} for x in entries]}

async def load_schedule(session:AsyncSession,schedule_id:str,organization_id:str)->tuple[RateSchedule,dict]:
 row=await session.scalar(select(RateSchedule).where(RateSchedule.id==schedule_id,RateSchedule.organization_id==organization_id,RateSchedule.status=="ACTIVE"))
 if row is None:raise EngineeringError("RATE_SCHEDULE_NOT_FOUND","Rate schedule not found")
 entries=list((await session.scalars(select(RateEntry).where(RateEntry.rate_schedule_id==row.id).order_by(RateEntry.item_code))).all())
 return row,schedule_out(row,entries)

async def calculate_all(session:AsyncSession,project:Project,version:ProjectVersion,world:WorldModelRevision,
 alt:DesignAlternative,geom:GeometryArtifact,actor:User,rate_schedule_id:str|None)->dict:
 ai=alt_input(world,alt);gi=geom_input(geom);geom_av=await session.get(ArtifactVersion,geom.artifact_version_id)
 await audit(session,project=project,version=version,actor=actor.id,action="QUANTITY_CALCULATION_REQUESTED",entity="design_alternative",entity_id=alt.id,metadata={"geometry_hash":geom.geometry_hash})
 qout=QENGINE.calculate(world.model_json,ai,gi)
 q=await session.scalar(select(QuantityArtifact).where(QuantityArtifact.project_version_id==version.id,QuantityArtifact.quantity_hash==qout["quantity_hash"]))
 q_reused=q is not None
 if q is None:
  qav=await new_artifact(session,project=project,version=version,world=world,actor=actor.id,artifact_type="quantity",payload=qout,dependencies=[geom_av],alternative_id=alt.id,status="CURRENT")
  q=QuantityArtifact(artifact_version_id=qav.id,project_id=project.id,project_version_id=version.id,world_model_revision_id=world.id,design_alternative_id=alt.id,geometry_artifact_id=geom.id,input_world_model_hash=ai["world_hash"],input_design_hash=ai["design_hash"],input_geometry_hash=geom.geometry_hash,engine_name=qout["engine_name"],engine_version=qout["engine_version"],config_version=qout["config_version"],quantity_hash=qout["quantity_hash"],status="CURRENT",assumptions_json=qout["assumptions"],unknowns_json=qout["unknowns"],uncertainty_json=qout["uncertainty"],provenance_json={"world_model_revision_id":world.id,"design_alternative_id":alt.id,"geometry_artifact_id":geom.id},payload_json=qout);session.add(q);await session.flush()
  await audit(session,project=project,version=version,actor=actor.id,action="QUANTITY_ARTIFACT_CREATED",entity="quantity_artifact",entity_id=q.id,metadata={"quantity_hash":q.quantity_hash})
 else:qav=await session.get(ArtifactVersion,q.artifact_version_id)
 try:sout=SENGINE.calculate(world.model_json,ai,gi)
 except Exception as exc:raise EngineeringError("STRUCTURAL_CONCEPT_FAILED","Preliminary structural concept generation failed") from exc
 s=await session.scalar(select(StructuralArtifact).where(StructuralArtifact.project_version_id==version.id,StructuralArtifact.concept_hash==sout["concept_hash"]))
 s_reused=s is not None
 if s is None:
  sav=await new_artifact(session,project=project,version=version,world=world,actor=actor.id,artifact_type="structural",payload=sout,dependencies=[geom_av],alternative_id=alt.id,status="CURRENT")
  s=StructuralArtifact(artifact_version_id=sav.id,project_id=project.id,project_version_id=version.id,world_model_revision_id=world.id,design_alternative_id=alt.id,geometry_artifact_id=geom.id,input_world_model_hash=ai["world_hash"],input_design_hash=ai["design_hash"],input_geometry_hash=geom.geometry_hash,engine_name=sout["engine_name"],engine_version=sout["engine_version"],config_version=sout["config_version"],concept_hash=sout["concept_hash"],status="CURRENT",assumptions_json=sout["assumptions"],warnings_json=sout["warnings"],unknowns_json=sout["unknowns"],provenance_json={"world_model_revision_id":world.id,"design_alternative_id":alt.id,"geometry_artifact_id":geom.id},payload_json=sout);session.add(s);await session.flush()
  await audit(session,project=project,version=version,actor=actor.id,action="STRUCTURAL_CONCEPT_GENERATED",entity="structural_artifact",entity_id=s.id,metadata={"concept_hash":s.concept_hash})
 else:sav=await session.get(ArtifactVersion,s.artifact_version_id)
 await audit(session,project=project,version=version,actor=actor.id,action="REGULATORY_EVALUATION_REQUESTED",entity="design_alternative",entity_id=alt.id,metadata={"world_model_hash":world.model_hash})
 try:rout=RENGINE.calculate(world.model_json,ai,gi)
 except Exception as exc:raise EngineeringError("REGULATORY_EVALUATION_FAILED","Regulatory evaluation failed") from exc
 r=await session.scalar(select(RegulatoryEvaluation).where(RegulatoryEvaluation.project_version_id==version.id,RegulatoryEvaluation.regulatory_hash==rout["regulatory_hash"]))
 r_reused=r is not None
 if r is None:
  rav=await new_artifact(session,project=project,version=version,world=world,actor=actor.id,artifact_type="regulatory",payload=rout,dependencies=[geom_av],alternative_id=alt.id,status="CURRENT")
  r=RegulatoryEvaluation(artifact_version_id=rav.id,project_id=project.id,project_version_id=version.id,world_model_revision_id=world.id,design_alternative_id=alt.id,geometry_artifact_id=geom.id,ruleset_id=None,input_world_model_hash=ai["world_hash"],input_design_hash=ai["design_hash"],input_geometry_hash=geom.geometry_hash,engine_name=rout["engine_name"],engine_version=rout["engine_version"],config_version=rout["config_version"],regulatory_hash=rout["regulatory_hash"],status="CURRENT",provenance_json={"world_model_revision_id":world.id,"ruleset":rout["ruleset"]},payload_json=rout);session.add(r);await session.flush()
  for x in rout["results"]:session.add(RegulatoryResult(evaluation_id=r.id,rule_id=None,rule_code=x["rule_code"],title=x["title"],applicability=x["applicability"],status=x["status"],observed_json=x["observed"],threshold_json=x["threshold"],unit=x["unit"],calculation=x["calculation"],reason=x["reason"],provenance_json=x["provenance"]))
  await audit(session,project=project,version=version,actor=actor.id,action="REGULATORY_EVALUATION_COMPLETED",entity="regulatory_evaluation",entity_id=r.id,metadata={"regulatory_hash":r.regulatory_hash,"overall":rout["overall_status"]})
 else:rav=await session.get(ArtifactVersion,r.artifact_version_id)
 cost=None;cost_error=None;c=None;cav=None;c_reused=False
 if rate_schedule_id:
  await audit(session,project=project,version=version,actor=actor.id,action="COST_CALCULATION_REQUESTED",entity="quantity_artifact",entity_id=q.id,metadata={"rate_schedule_id":rate_schedule_id})
  schedule_row,schedule=await load_schedule(session,rate_schedule_id,project.organization_id);cost=CENGINE.calculate(qout,schedule)
  c=await session.scalar(select(CostEstimate).where(CostEstimate.project_version_id==version.id,CostEstimate.cost_hash==cost["cost_hash"]));c_reused=c is not None
  if c is None:
   cav=await new_artifact(session,project=project,version=version,world=world,actor=actor.id,artifact_type="cost",payload=cost,dependencies=[qav],alternative_id=alt.id,status="CURRENT")
   c=CostEstimate(artifact_version_id=cav.id,project_id=project.id,project_version_id=version.id,world_model_revision_id=world.id,design_alternative_id=alt.id,geometry_artifact_id=geom.id,quantity_artifact_id=q.id,rate_schedule_id=schedule_row.id,input_quantity_hash=q.quantity_hash or "",input_rate_schedule_hash=cost["input_rate_schedule_hash"],engine_name=cost["engine_name"],engine_version=cost["engine_version"],config_version=cost["config_version"],cost_hash=cost["cost_hash"],currency=cost["currency"],direct_cost=cost["direct_cost"],total_cost=cost["total_cost"],low_estimate=cost["low_estimate"],high_estimate=cost["high_estimate"],status="CURRENT",assumptions_json=cost["assumptions"],unknowns_json=cost["unknowns"],uncertainty_json=cost["uncertainty"],provenance_json={"quantity_artifact_id":q.id,"rate_schedule_id":schedule_row.id,"rate_schedule_hash":schedule_hash(schedule)},payload_json=cost);session.add(c);await session.flush()
   await audit(session,project=project,version=version,actor=actor.id,action="COST_ESTIMATE_CREATED",entity="cost_estimate",entity_id=c.id,metadata={"cost_hash":c.cost_hash,"rate_schedule_id":schedule_row.id})
  else:cav=await session.get(ArtifactVersion,c.artifact_version_id)
 else:cost_error={"code":"COST_UNAVAILABLE","message":"No rate schedule selected. No market rate or cost has been invented.","missing_data":["rate_schedule_id"],"required_input":"Select an explicitly sourced user, demo, or verified rate schedule."}
 vout=VENGINE.calculate(gi,qout,sout,rout,cost,cost_error);v=await session.scalar(select(ValidationRun).where(ValidationRun.project_version_id==version.id,ValidationRun.validation_hash==vout["validation_hash"]));v_reused=v is not None
 if v is None:
  deps=[geom_av,qav,sav,rav]+([cav] if cav else []);vav=await new_artifact(session,project=project,version=version,world=world,actor=actor.id,artifact_type="engineering_validation",payload=vout,dependencies=deps,alternative_id=alt.id,status="CURRENT")
  v=ValidationRun(artifact_version_id=vav.id,project_id=project.id,project_version_id=version.id,world_model_revision_id=world.id,design_alternative_id=alt.id,input_hashes_json=vout["input_hashes"],engine_name=vout["engine_name"],engine_version=vout["engine_version"],config_version=vout["config_version"],validation_hash=vout["validation_hash"],status="CURRENT",provenance_json={"world_model_revision_id":world.id,"alternative_id":alt.id},payload_json=vout);session.add(v);await session.flush()
  source_ids={"geometry":geom.id,"quantity":q.id,"cost":c.id if c else None,"structural":s.id,"regulatory":r.id}
  for x in vout["checks"]:session.add(ValidationCheck(validation_run_id=v.id,code=x["code"],severity=x["severity"],category=x["category"],status=x["status"],message=x["message"],source_artifact_id=source_ids.get(x["source_artifact"]),evidence_ids_json=x["evidence"]))
  await audit(session,project=project,version=version,actor=actor.id,action="PHASE3_VALIDATION_COMPLETED",entity="validation_run",entity_id=v.id,metadata={"validation_hash":v.validation_hash,"status":vout["status"]})
 await session.commit();logger.info("phase3_engineering_completed",extra={"project_id":project.id,"project_version_id":version.id,"alternative_id":alt.id,"quantity_hash":qout["quantity_hash"],"cost_hash":cost.get("cost_hash") if cost else None,"structural_hash":sout["concept_hash"],"regulatory_hash":rout["regulatory_hash"]})
 return await summary(session,project,version,world,alt,geom,rate_schedule_id,{"quantity":q_reused,"cost":c_reused,"structure":s_reused,"regulatory":r_reused,"validation":v_reused},cost_error)

async def summary(session,project,version,world,alt,geom,rate_schedule_id=None,reused=None,cost_error=None):
 q=await session.scalar(select(QuantityArtifact).where(QuantityArtifact.design_alternative_id==alt.id).order_by(QuantityArtifact.created_at.desc()))
 s=await session.scalar(select(StructuralArtifact).where(StructuralArtifact.design_alternative_id==alt.id).order_by(StructuralArtifact.created_at.desc()))
 r=await session.scalar(select(RegulatoryEvaluation).where(RegulatoryEvaluation.design_alternative_id==alt.id).order_by(RegulatoryEvaluation.created_at.desc()))
 c=None
 if rate_schedule_id:c=await session.scalar(select(CostEstimate).where(CostEstimate.design_alternative_id==alt.id,CostEstimate.rate_schedule_id==rate_schedule_id).order_by(CostEstimate.created_at.desc()))
 elif q:c=await session.scalar(select(CostEstimate).where(CostEstimate.design_alternative_id==alt.id,CostEstimate.quantity_artifact_id==q.id).order_by(CostEstimate.created_at.desc()))
 v=await session.scalar(select(ValidationRun).where(ValidationRun.design_alternative_id==alt.id).order_by(ValidationRun.created_at.desc()))
 def data(row):
  if not row:return None
  payload=dict(row.payload_json);payload.update({"id":row.id,"artifact_version_id":row.artifact_version_id,"status":row.status,"created_at":row.created_at,"current":row.status=="CURRENT"});return payload
 return {"project_id":project.id,"project_version_id":version.id,"alternative":{"id":alt.id,"name":alt.name,"status":alt.status,"design_hash":alt.design_hash,"metrics":alt.key_metrics_json},"geometry":{"id":geom.id,"status":geom.status,"geometry_hash":geom.geometry_hash},"quantity":data(q),"cost":data(c),"cost_error":cost_error if c is None else None,"structure":data(s),"regulatory":data(r),"validation":data(v),"reused":reused or {},"notice":"Preliminary feasibility intelligence only. Not construction documentation, structural certification, regulatory approval, or market-price assurance."}
