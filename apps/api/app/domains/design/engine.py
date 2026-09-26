from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ArtifactDependency, ArtifactVersion, DesignAlternative, DesignConstraintRecord, DesignGenerationRun,
    GeometryArtifact, Project, ProjectVersion, User, WorldModelRevision,
    QuantityArtifact, CostEstimate, StructuralArtifact, RegulatoryEvaluation, ValidationRun,
)
from app.domains.design.config import DEFAULT_CONFIG, DesignEngineConfig
from app.domains.design.constraints import DesignConstraintResolver, ResolvedDesignContext
from app.domains.design.geometry_ir import GeometryValidator, MassingGeometryEngine
from app.domains.design.strategies import STRATEGIES, DesignCandidate
from app.domains.foundation.service import audit
from app.domains.lifecycle.service import canonical_hash, new_artifact

logger = logging.getLogger("design_engine")


class DesignGenerationError(Exception):
    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None):
        self.code, self.message, self.context = code, message, context or {}
        super().__init__(message)


class ComputationalDesignEngine:
    def __init__(self, config: DesignEngineConfig = DEFAULT_CONFIG):
        self.config = config
        self.resolver = DesignConstraintResolver(config)
        self.geometry_engine = MassingGeometryEngine(config)
        self.geometry_validator = GeometryValidator(config)

    def generation_key(self, world_hash: str) -> str:
        return canonical_hash({"world_model_hash":world_hash,"engine_version":self.config.engine_version,
            "config":self.config.canonical(),"strategies":[(s.id,s.version) for s in STRATEGIES]})

    async def generate(self, session: AsyncSession, project: Project, version: ProjectVersion,
                       world: WorldModelRevision, actor: User) -> DesignGenerationRun:
        key = self.generation_key(world.model_hash or "")
        existing = await session.scalar(select(DesignGenerationRun).where(
            DesignGenerationRun.project_version_id==version.id, DesignGenerationRun.generation_key==key))
        if existing and existing.status == "COMPLETED":
            existing._idempotent_reuse = True
            return existing
        if existing and existing.status == "GENERATING":
            raise DesignGenerationError("DESIGN_GENERATION_IN_PROGRESS",
                "An identical design generation is already in progress", {"generation_id":existing.id})
        if existing:
            # A retry reuses the stable generation identity and removes diagnostics from the prior failed attempt.
            await session.execute(delete(DesignConstraintRecord).where(DesignConstraintRecord.generation_run_id==existing.id))
            existing.status="GENERATING"; existing.progress_json=[]; existing.error_code=None
            existing.error_message=None; existing.completed_at=None; existing.world_model_revision_id=world.id
            existing.requested_by=actor.id
            run=existing
        else:
            run = DesignGenerationRun(organization_id=project.organization_id,project_id=project.id,
                project_version_id=version.id,world_model_revision_id=world.id,world_model_hash=world.model_hash or "",
                generation_key=key,engine_version=self.config.engine_version,config_version=self.config.config_version,
                status="GENERATING",progress_json=[],requested_by=actor.id)
            session.add(run)
        await session.flush()
        await audit(session,project=project,version=version,actor=actor.id,action="DESIGN_GENERATION_REQUESTED",
            entity="design_generation_run",entity_id=run.id,metadata={"world_model_hash":world.model_hash,"engine_version":self.config.engine_version})
        self._stage(run,"resolve_world_model",{"world_model_revision_id":world.id,"world_model_hash":world.model_hash})
        logger.info("design_generation_started",extra={"project_id":project.id,"project_version_id":version.id,"generation_id":run.id,"engine_version":self.config.engine_version})
        # Persist the run before expensive work so even an unexpected failure has a durable lifecycle record.
        await session.commit()
        run_id = run.id
        project_id, version_id, actor_id = project.id, version.id, actor.id
        run._idempotent_reuse = False
        try:
            await self._mark_hash_mismatch_stale(session,version.id,world.model_hash or "",project,version,actor.id)
            context=self.resolver.resolve(world.model_json,world.model_hash or "")
            self._stage(run,"resolve_design_constraints",{"constraint_count":len(context.constraints),"conflicts":context.conflicts})
            for item in context.constraints:
                session.add(DesignConstraintRecord(generation_run_id=run.id,project_version_id=version.id,
                    world_model_revision_id=world.id,source_reference=item.source_reference,parameter=item.parameter,
                    value_json=item.value,unit=item.unit,classification=item.classification,operator=item.operator,
                    severity=item.severity,rationale=item.rationale,provenance_json=item.provenance))
            if context.conflicts:
                raise DesignGenerationError("DESIGN_CONSTRAINT_CONFLICT","Design constraints cannot produce bounded valid geometry",{"conflicts":context.conflicts})
            target=float(next((c.value for c in context.constraints if c.parameter=="target_gfa" and c.value is not None),
                context.search_space.site_width_m*context.search_space.site_depth_m*self.config.default_target_coverage*self.config.default_floor_count))
            floors=int(next(v.preferred_value for v in context.search_space.variables if v.name=="floor_count"))
            floor_height=float(next(v.preferred_value for v in context.search_space.variables if v.name=="floor_to_floor_height"))
            parking=next((int(c.value) for c in context.constraints if c.parameter=="parking_spaces" and c.value is not None),None)
            generated=[]
            for strategy in STRATEGIES:
                generated.extend(strategy.generate_candidates(context,self.config,target,floors,floor_height,parking))
            self._stage(run,"generate_candidates",{"candidate_count":len(generated),"strategy_ids":[s.id for s in STRATEGIES]})
            selected=self._select_diverse(generated)
            self._stage(run,"validate_candidates",{"valid_candidate_count":sum(c.valid for c in generated),"selected_count":len(selected),
                "invalid":[{"candidate":c.candidate_key,"reasons":c.invalid_reasons} for c in generated if not c.valid]})
            if len(selected)<2:
                raise DesignGenerationError("NO_VALID_CANDIDATE","Fewer than two materially different valid candidates were generated",
                    {"invalid_candidates":[{"candidate":c.candidate_key,"reasons":c.invalid_reasons} for c in generated if not c.valid]})
            prepared_geometry: dict[str, tuple[str, Any, Any]] = {}
            for candidate in selected:
                design_hash=self._design_hash(world.model_hash or "",candidate)
                geometry=self.geometry_engine.generate(candidate,design_hash,context.search_space.site_width_m,context.search_space.site_depth_m)
                validation=self.geometry_validator.validate(geometry,candidate)
                if not validation.valid:
                    logger.warning("geometry_validation_failed",extra={"generation_id":run.id,"candidate":candidate.candidate_key,"errors":validation.errors})
                    raise DesignGenerationError("GEOMETRY_VALIDATION_FAILED","Generated geometry failed deterministic validation",
                        {"candidate":candidate.candidate_key,"errors":validation.errors})
                prepared_geometry[candidate.candidate_key]=(design_hash,geometry,validation)
            alt_ids=[]
            for index,candidate in enumerate(selected,1):
                design_hash,geometry,validation=prepared_geometry[candidate.candidate_key]
                alt_av=await new_artifact(session,project=project,version=version,world=world,actor=actor.id,
                    artifact_type="design_alternative",payload={"design_hash":design_hash,"parameters":candidate.parameters,
                    "metrics":candidate.metrics},status="CURRENT")
                strategy=next(s for s in STRATEGIES if s.id==candidate.strategy_id)
                alt=DesignAlternative(artifact_version_id=alt_av.id,project_id=project.id,project_version_id=version.id,
                    world_model_revision_id=world.id,generation_run_id=run.id,name=f"{strategy.name} {index}",
                    description=strategy.description,strategy_id=strategy.id,strategy_version=strategy.version,
                    design_parameters_json=candidate.parameters,key_metrics_json=candidate.metrics,
                    constraint_results_json=candidate.constraint_results,reasoning_json=candidate.reasoning,
                    assumptions_json=candidate.assumptions,unknowns_json=candidate.unknowns,tradeoffs_json=candidate.tradeoffs,
                    design_engine_version=self.config.engine_version,design_engine_config_version=self.config.config_version,
                    input_world_model_hash=world.model_hash or "",design_hash=design_hash,
                    provenance_json={"world_model_revision_id":world.id,"world_model_hash":world.model_hash,
                        "generation_run_id":run.id,"candidate_key":candidate.candidate_key,"deterministic":True},
                    status="VALID",payload_json={"parameters":candidate.parameters,"metrics":candidate.metrics})
                session.add(alt); await session.flush(); alt_av.alternative_id=alt.id
                ir=geometry.model_dump(mode="json")
                geometry_hash=canonical_hash({"geometry_ir":ir,"geometry_engine_version":self.config.geometry_engine_version,"design_hash":design_hash})
                geom_av=await new_artifact(session,project=project,version=version,world=world,actor=actor.id,
                    artifact_type="geometry",payload={"geometry_ir":ir,"validation":validation.model_dump(mode="json")},
                    dependencies=[alt_av],alternative_id=alt.id,status="CURRENT")
                geom_av.output_hash=geometry_hash
                geom=GeometryArtifact(artifact_version_id=geom_av.id,project_id=project.id,project_version_id=version.id,
                    alternative_id=alt.id,world_model_revision_id=world.id,geometry_hash=geometry_hash,
                    input_world_model_hash=world.model_hash or "",design_hash=design_hash,
                    engine_name=self.config.geometry_engine_name,engine_version=self.config.geometry_engine_version,
                    status="CURRENT",provenance_json={"world_model_revision_id":world.id,"world_model_hash":world.model_hash,
                        "design_alternative_id":alt.id,"design_hash":design_hash,"generation_run_id":run.id},
                    payload_json={"geometry_ir":ir,"validation":validation.model_dump(mode="json")})
                session.add(geom); await session.flush(); alt_ids.append(alt.id)
                await audit(session,project=project,version=version,actor=actor.id,action="ALTERNATIVE_CREATED",
                    entity="design_alternative",entity_id=alt.id,metadata={"strategy":strategy.id,"design_hash":design_hash})
                await audit(session,project=project,version=version,actor=actor.id,action="GEOMETRY_CREATED",
                    entity="geometry_artifact",entity_id=geom.id,metadata={"alternative_id":alt.id,"geometry_hash":geometry_hash})
                logger.info("alternative_created",extra={"project_id":project.id,"project_version_id":version.id,"generation_id":run.id,"alternative_id":alt.id})
                logger.info("geometry_created",extra={"alternative_id":alt.id,"geometry_hash":geometry_hash})
            self._stage(run,"generate_and_validate_geometry",{"geometry_count":len(alt_ids)})
            self._stage(run,"persist_artifacts",{"alternative_ids":alt_ids})
            run.generated_alternative_ids_json=alt_ids; run.status="COMPLETED"; run.completed_at=datetime.now(timezone.utc)
            await audit(session,project=project,version=version,actor=actor.id,action="DESIGN_GENERATION_COMPLETED",
                entity="design_generation_run",entity_id=run.id,metadata={"alternative_ids":alt_ids})
            await session.commit()
            logger.info("design_generation_completed",extra={"project_id":project.id,"project_version_id":version.id,"generation_id":run.id,"alternative_count":len(alt_ids)})
            return run
        except DesignGenerationError as exc:
            run.status="FAILED";run.error_code=exc.code;run.error_message=exc.message;run.completed_at=datetime.now(timezone.utc)
            self._stage(run,"failed",{"code":exc.code,"message":exc.message,"context":exc.context})
            await audit(session,project=project,version=version,actor=actor.id,action="DESIGN_GENERATION_FAILED",
                entity="design_generation_run",entity_id=run.id,metadata={"code":exc.code,"message":exc.message})
            await session.commit()
            logger.error("design_generation_failed",extra={"project_id":project.id,"project_version_id":version.id,"generation_id":run.id,"error_code":exc.code})
            raise
        except Exception as exc:
            # Discard any partially staged alternatives/artifacts, then durably mark the already-created run failed.
            await session.rollback()
            failed = await session.get(DesignGenerationRun, run_id)
            if failed is not None:
                failed.status="FAILED"; failed.error_code="DESIGN_GENERATION_INTERNAL_ERROR"
                failed.error_message="Design generation failed unexpectedly; retry or contact support"
                failed.completed_at=datetime.now(timezone.utc)
                self._stage(failed,"failed",{"code":failed.error_code,"message":failed.error_message})
                failed_project = await session.get(Project, project_id)
                failed_version = await session.get(ProjectVersion, version_id)
                if failed_project is not None and failed_version is not None:
                    await audit(session,project=failed_project,version=failed_version,actor=actor_id,
                        action="DESIGN_GENERATION_FAILED",entity="design_generation_run",entity_id=failed.id,
                        metadata={"code":failed.error_code})
                await session.commit()
            logger.exception("design_generation_internal_error",extra={"project_id":project_id,
                "project_version_id":version_id,"generation_id":run_id})
            raise DesignGenerationError("DESIGN_GENERATION_INTERNAL_ERROR",
                "Design generation failed unexpectedly; retry or contact support",{"generation_id":run_id}) from exc

    def _design_hash(self,world_hash:str,candidate:DesignCandidate)->str:
        return canonical_hash({"world_model_hash":world_hash,"strategy_id":candidate.strategy_id,
            "strategy_version":candidate.strategy_version,"parameters":candidate.parameters,
            "engine_version":self.config.engine_version,"config_version":self.config.config_version})

    def _select_diverse(self,candidates:list[DesignCandidate])->list[DesignCandidate]:
        chosen=[]; hashes=set()
        for strategy in STRATEGIES:
            valid=sorted((c for c in candidates if c.strategy_id==strategy.id and c.valid),key=lambda c:(c.score,c.candidate_key))
            for candidate in valid:
                signature=canonical_hash({"parameters":candidate.parameters,"metrics":candidate.metrics})
                if signature not in hashes:
                    hashes.add(signature);chosen.append(candidate);break
        return chosen

    def _stage(self,run:DesignGenerationRun,name:str,details:dict[str,Any])->None:
        run.progress_json=[*run.progress_json,{"stage":name,"status":"COMPLETED","at":datetime.now(timezone.utc).isoformat(),"details":details}]

    async def _mark_hash_mismatch_stale(self,session:AsyncSession,version_id:str,current_hash:str,
                                        project:Project,version:ProjectVersion,actor:str)->None:
        alternatives=list((await session.scalars(select(DesignAlternative).where(
            DesignAlternative.project_version_id==version_id,DesignAlternative.input_world_model_hash!=current_hash,
            DesignAlternative.status.in_(["VALID","SELECTED"])))).all())
        if not alternatives:return
        ids=[a.id for a in alternatives]
        for alt in alternatives:alt.status="STALE"
        geometries=list((await session.scalars(select(GeometryArtifact).where(GeometryArtifact.alternative_id.in_(ids)))).all())
        for geom in geometries:geom.status="STALE"
        geometry_ids=[g.id for g in geometries]
        quantities=list((await session.scalars(select(QuantityArtifact).where(QuantityArtifact.geometry_artifact_id.in_(geometry_ids)))).all()) if geometry_ids else []
        structures=list((await session.scalars(select(StructuralArtifact).where(StructuralArtifact.geometry_artifact_id.in_(geometry_ids)))).all()) if geometry_ids else []
        regulations=list((await session.scalars(select(RegulatoryEvaluation).where(RegulatoryEvaluation.geometry_artifact_id.in_(geometry_ids)))).all()) if geometry_ids else []
        quantity_ids=[q.id for q in quantities]
        costs=list((await session.scalars(select(CostEstimate).where(CostEstimate.quantity_artifact_id.in_(quantity_ids)))).all()) if quantity_ids else []
        validations=list((await session.scalars(select(ValidationRun).where(ValidationRun.design_alternative_id.in_(ids)))).all())
        downstream=[*quantities,*costs,*structures,*regulations,*validations]
        for artifact in downstream:artifact.status="STALE"
        av_ids=[a.artifact_version_id for a in alternatives]+[g.artifact_version_id for g in geometries]+[x.artifact_version_id for x in downstream]
        artifact_versions=list((await session.scalars(select(ArtifactVersion).where(ArtifactVersion.id.in_(av_ids)))).all())
        for av in artifact_versions:av.status="STALE"
        await audit(session,project=project,version=version,actor=actor,action="GEOMETRY_INVALIDATED",
            entity="project_version",entity_id=version.id,metadata={"stale_alternative_ids":ids,"reason":"world_model_hash_changed"})


ENGINE=ComputationalDesignEngine()
