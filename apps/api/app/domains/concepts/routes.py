from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.db.models import ArtifactVersion, DesignAlternative, DesignGenerationRun, User
from app.db.site_models import SiteRevision
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.design.engine import ENGINE, DesignGenerationError
from app.domains.foundation.service import error, resolve_project_version, resolve_world_model

router = APIRouter(tags=["concepts"])

async def _inputs(session, version_id: str):
    program = await session.scalar(select(ArtifactVersion).where(ArtifactVersion.project_version_id == version_id,
        ArtifactVersion.artifact_type == "architectural_program", ArtifactVersion.status == "current").order_by(ArtifactVersion.version.desc()).limit(1))
    envelope = await session.scalar(select(ArtifactVersion).where(ArtifactVersion.project_version_id == version_id,
        ArtifactVersion.artifact_type == "planning_envelope", ArtifactVersion.status == "current").order_by(ArtifactVersion.version.desc()).limit(1))
    if program is None: raise error(409, "PROGRAM_REQUIRED", "Generate and review the architectural program before concept generation")
    if envelope is None: raise error(409, "ENVELOPE_REQUIRED", "Generate and review the planning envelope before concept generation")
    return program, envelope

@router.post("/projects/{project_id}/versions/{version_ref}/concepts/generate")
async def generate_concepts(project_id: str, version_ref: str, user: User = Depends(current_user), session=Depends(get_session)):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    world = await resolve_world_model(session, version.id)
    program, envelope = await _inputs(session, version.id)
    try:
        run = await ENGINE.generate(
            session,
            project,
            version,
            world,
            user,
            input_artifacts={"program": program, "envelope": envelope},
        )
    except DesignGenerationError as exc:
        raise error(409, exc.code, exc.message, **exc.context) from exc
    alternatives = list((await session.scalars(select(DesignAlternative).where(DesignAlternative.generation_run_id == run.id))).all())
    envelope_data = envelope.payload_json
    max_gfa = envelope_data.get("max_gfa_m2")
    buildable = envelope_data.get("buildable_area_m2")
    for alt in alternatives:
        metrics = alt.key_metrics_json
        failures=[]
        if max_gfa is not None and float(metrics.get("gross_floor_area_m2", 0)) > float(max_gfa) + 1e-6: failures.append("MAX_GFA_EXCEEDED")
        if buildable is not None and float(metrics.get("building_footprint_m2", 0)) > float(buildable) + 1e-6: failures.append("BUILDABLE_FOOTPRINT_EXCEEDED")
        if failures:
            alt.status="INVALID"
            alt.constraint_results_json=[*alt.constraint_results_json,{"parameter":"s2_envelope","status":"FAIL","reasons":failures}]
        alt.provenance_json={**alt.provenance_json,"program_artifact_id":program.id,"program_hash":program.output_hash,
            "envelope_artifact_id":envelope.id,"envelope_hash":envelope.output_hash}
    await session.commit()
    valid=[a for a in alternatives if a.status == "VALID"]
    return {"generation_id":run.id,"status":run.status,"world_model_hash":world.model_hash,
        "program_hash":program.output_hash,"envelope_hash":envelope.output_hash,
        "alternatives":[{"id":a.id,"name":a.name,"strategy_id":a.strategy_id,"status":a.status,"metrics":a.key_metrics_json,
            "constraint_results":a.constraint_results_json,"assumptions":a.assumptions_json,"unknowns":a.unknowns_json,
            "tradeoffs":a.tradeoffs_json,"reasoning":a.reasoning_json,"design_hash":a.design_hash} for a in alternatives],
        "valid_alternative_count":len(valid),"selection_notice":"Alternatives are preliminary design directions; no automatic optimum or regulatory approval is claimed."}

@router.get("/projects/{project_id}/versions/{version_ref}/concepts")
async def list_concepts(project_id: str, version_ref: str, user: User = Depends(current_user), session=Depends(get_session)):
    _, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    rows = list((await session.scalars(select(DesignAlternative).where(DesignAlternative.project_version_id == version.id)
        .order_by(DesignAlternative.created_at.desc()))).all())
    return {"world_model_hash":world.model_hash,"alternatives":[{"id":r.id,"name":r.name,"strategy_id":r.strategy_id,
        "status":r.status,"metrics":r.key_metrics_json,"constraints":r.constraint_results_json,"tradeoffs":r.tradeoffs_json,
        "assumptions":r.assumptions_json,"unknowns":r.unknowns_json,"reasoning":r.reasoning_json,"design_hash":r.design_hash,
        "provenance":r.provenance_json} for r in rows]}
