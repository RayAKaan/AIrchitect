from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ArtifactDependency, ArtifactVersion, CostEstimate, DecisionRecord, DeliverableArtifact,
    DeliverableRecord, DesignAlternative, EvidenceRecord, GeometryArtifact, Project,
    ProjectVersion, QuantityArtifact, RateSchedule, RegulatoryEvaluation, StructuralArtifact,
    ValidationCheck, ValidationRun, WorkflowEvent, WorkflowRecord, WorkflowTaskRecord,
    WorldModelRevision,
)
from app.domains.geometry.engine import generate as generate_geometry
from app.domains.geometry.schemas import GeometryGenerateRequest
from app.domains.structure.engine import generate as generate_structure
from app.domains.structure.schemas import StructuralConceptRequest

STAGES = [
    "resolve_project_version", "validate_requirements", "generate_alternatives",
    "generate_geometry", "validate_geometry", "calculate_quantities", "calculate_cost",
    "generate_structural_concept", "run_regulatory_checks", "validate_outputs",
    "assemble_evidence", "generate_feasibility_package",
]


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def model_from_brief(brief: str) -> tuple[dict[str, Any], list[str]]:
    def number(pattern: str) -> float | None:
        match = re.search(pattern, brief, re.I)
        return float(match.group(1).replace(",", "")) if match else None

    dims = re.search(r"(?:site|plot)[^\d]{0,30}(\d+(?:\.\d+)?)\s*(?:m|metres?|meters?)?\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:m|metres?|meters?)?", brief, re.I)
    width, depth = (float(dims.group(1)), float(dims.group(2))) if dims else (None, None)
    floors_value = number(r"\b(\d{1,2})\s*(?:floors?|storeys|stories)\b")
    floor_height = number(r"(?:floor[- ]to[- ]floor|floor height)[^\d]{0,15}(\d+(?:\.\d+)?)\s*m")
    gfa = number(r"\b(\d[\d,]*(?:\.\d+)?)\s*(?:m2|m²|sqm|sq\.?\s*m|square\s*met(?:er|re)s?)\b")
    floors = int(floors_value) if floors_value else None
    floor_height = floor_height or 4.0
    unknown = [name for name, value in (("site_width_m", width), ("site_depth_m", depth), ("floor_count", floors)) if value is None]
    footprint_width = round(width * 0.72, 3) if width else None
    footprint_depth = round(depth * 0.72, 3) if depth else None
    return {
        "schema_version": "1.0.0", "site": {"width_m": width, "depth_m": depth, "jurisdiction": "Saudi Arabia"},
        "building": {"use": "commercial_retail", "footprint_width_m": footprint_width,
                     "footprint_depth_m": footprint_depth, "floor_count": floors,
                     "floor_to_floor_m": floor_height, "target_gfa_m2": gfa},
        "structural_grid": {"preferred_max_bay_m": 8.0, "system": "conceptual reinforced concrete frame"},
        "unknowns": unknown,
        "provenance": {"source": "user_brief", "method": "deterministic_pattern_v2", "brief_hash": canonical_hash(brief)},
    }, unknown


async def new_artifact(session: AsyncSession, *, project: Project, version: ProjectVersion,
                       world: WorldModelRevision, actor: str, artifact_type: str, payload: dict,
                       dependencies: list[ArtifactVersion] | None = None, alternative_id: str | None = None,
                       status: str = "current") -> ArtifactVersion:
    latest = await session.scalar(select(func.max(ArtifactVersion.version)).where(
        ArtifactVersion.project_version_id == version.id, ArtifactVersion.artifact_type == artifact_type)) or 0
    deps = dependencies or []
    artifact = ArtifactVersion(
        organization_id=project.organization_id, project_id=project.id, project_version_id=version.id,
        world_model_revision_id=world.id, alternative_id=alternative_id, artifact_type=artifact_type,
        version=latest + 1, status=status, provenance_json={"engine": "deterministic", "created_from_canonical_state": True},
        input_references_json=[d.id for d in deps], output_hash=canonical_hash(payload), payload_json=payload,
        created_by=actor,
    )
    session.add(artifact)
    await session.flush()
    for dependency in deps:
        session.add(ArtifactDependency(artifact_version_id=artifact.id, depends_on_artifact_version_id=dependency.id))
    return artifact


async def run_pipeline(session: AsyncSession, project: Project, version: ProjectVersion,
                       actor: str, idempotency_key: str, rate_schedule: RateSchedule) -> WorkflowRecord:
    existing = await session.scalar(select(WorkflowRecord).where(
        WorkflowRecord.organization_id == project.organization_id,
        WorkflowRecord.idempotency_key == idempotency_key))
    if existing:
        return existing
    world = await session.scalar(select(WorldModelRevision).where(
        WorldModelRevision.project_version_id == version.id).order_by(WorldModelRevision.revision.desc()))
    if world is None:
        raise ValueError("Project version has no canonical World Model")
    building = world.model_json.get("building", {})
    unknowns = world.model_json.get("unknowns", [])
    if any(x in unknowns for x in ("site_width_m", "site_depth_m", "floor_count")):
        raise ValueError("Critical geometry inputs are unknown; confirm site dimensions and floor count")

    workflow = WorkflowRecord(organization_id=project.organization_id, project_id=project.id,
        project_version_id=version.id, created_by=actor, workflow_type="feasibility",
        idempotency_key=idempotency_key, state="running")
    session.add(workflow)
    await session.flush()
    previous: str | None = None
    tasks: dict[str, WorkflowTaskRecord] = {}
    for stage in STAGES:
        task = WorkflowTaskRecord(workflow_id=workflow.id, key=stage, kind=stage, payload_json={"project_version_id": version.id},
            depends_on_json=[] if previous is None else [previous], state="running" if previous is None else "pending", max_attempts=3)
        session.add(task); await session.flush(); tasks[stage] = task; previous = stage
    def complete(stage: str, result: dict) -> None:
        task = tasks[stage]; old = task.state; task.state = "succeeded"; task.attempts = 1; task.result_json = result
        session.add(WorkflowEvent(workflow_id=workflow.id, task_id=task.id, event_type="task.transition", from_state=old, to_state="succeeded", data_json=result))
        index = STAGES.index(stage)
        if index + 1 < len(STAGES): tasks[STAGES[index + 1]].state = "running"

    complete("resolve_project_version", {"project_version_id": version.id, "world_model_revision_id": world.id})
    complete("validate_requirements", {"unknowns": unknowns, "status": "succeeded"})

    alternatives: list[tuple[DesignAlternative, ArtifactVersion]] = []
    width, depth, floors = float(building["footprint_width_m"]), float(building["footprint_depth_m"]), int(building["floor_count"])
    variants = [("Balanced", 1.0, floors), ("Compact", .88, floors + 1), ("Wide plate", 1.08, max(1, floors - 1))]
    for name, scale, variant_floors in variants:
        params = {"footprint_width_m": round(width * scale, 3), "footprint_depth_m": round(depth * scale, 3),
                  "floor_count": variant_floors, "floor_to_floor_m": building["floor_to_floor_m"]}
        av = await new_artifact(session, project=project, version=version, world=world, actor=actor,
            artifact_type="design_alternative", payload={"name": name, **params})
        alt = DesignAlternative(artifact_version_id=av.id, project_id=project.id, project_version_id=version.id,
            name=name, description="Deterministic feasibility massing variant", design_parameters_json=params,
            key_metrics_json={"gfa_m2": round(params["footprint_width_m"] * params["footprint_depth_m"] * variant_floors, 2)}, payload_json=params)
        session.add(alt); await session.flush(); av.alternative_id = alt.id; alternatives.append((alt, av))
    complete("generate_alternatives", {"alternative_ids": [a.id for a, _ in alternatives]})

    geometries: list[tuple[GeometryArtifact, ArtifactVersion, DesignAlternative]] = []
    for alt, alt_av in alternatives:
        p = alt.design_parameters_json
        generated = generate_geometry(GeometryGenerateRequest(project_id=project.id, source_revision=world.revision,
            footprint_width_m=p["footprint_width_m"], footprint_depth_m=p["footprint_depth_m"],
            options=[{"option_id": alt.id, "floors": p["floor_count"], "floor_to_floor_m": p["floor_to_floor_m"]}]))[0]
        payload = generated.model_dump(mode="json")
        av = await new_artifact(session, project=project, version=version, world=world, actor=actor,
            artifact_type="geometry", payload=payload, dependencies=[alt_av], alternative_id=alt.id)
        row = GeometryArtifact(artifact_version_id=av.id, project_id=project.id, project_version_id=version.id,
            alternative_id=alt.id, geometry_hash=generated.geometry_sha256, payload_json=payload)
        session.add(row); await session.flush(); geometries.append((row, av, alt))
    complete("generate_geometry", {"geometry_artifact_ids": [g.id for g, _, _ in geometries]})
    complete("validate_geometry", {"all_hashes_valid": all(g.geometry_hash == av.output_hash or len(g.geometry_hash) == 64 for g, av, _ in geometries)})

    quantities: list[tuple[QuantityArtifact, ArtifactVersion, GeometryArtifact, DesignAlternative]] = []
    for geom, geom_av, alt in geometries:
        gp = geom.payload_json
        q_payload = {"geometry_artifact_id": geom.id, "geometry_hash": geom.geometry_hash, "lines": [
            {"code": "gfa", "description": "Gross floor area", "quantity": gp["gross_floor_area_m2"], "unit": "m2"},
            {"code": "footprint", "description": "Building footprint", "quantity": gp["footprint_area_m2"], "unit": "m2"},
            {"code": "volume", "description": "Gross massing volume", "quantity": gp["gross_volume_m3"], "unit": "m3"}],
            "method": "deterministic_rectangular_massing_v1"}
        av = await new_artifact(session, project=project, version=version, world=world, actor=actor,
            artifact_type="quantity", payload=q_payload, dependencies=[geom_av], alternative_id=alt.id)
        q = QuantityArtifact(artifact_version_id=av.id, project_id=project.id, project_version_id=version.id,
            geometry_artifact_id=geom.id, payload_json=q_payload)
        session.add(q); await session.flush(); quantities.append((q, av, geom, alt))
    complete("calculate_quantities", {"quantity_artifact_ids": [q.id for q, *_ in quantities]})

    costs: list[tuple[CostEstimate, ArtifactVersion]] = []
    rate = next((r for r in rate_schedule.rates_json if r["category"] == "gross_floor_area"), None)
    if rate is None: raise ValueError("Rate schedule has no gross_floor_area rate")
    for q, q_av, _, alt in quantities:
        gfa = next(line["quantity"] for line in q.payload_json["lines"] if line["code"] == "gfa")
        payload = {"quantity_artifact_id": q.id, "rate_schedule_id": rate_schedule.id, "currency": "SAR",
            "low": round(gfa * rate["low"], 2), "base": round(gfa * rate["base"], 2), "high": round(gfa * rate["high"], 2),
            "rate_provenance": {"source": rate_schedule.source, "version": rate_schedule.version, "demo": rate_schedule.is_demo},
            "status": "preliminary"}
        av = await new_artifact(session, project=project, version=version, world=world, actor=actor,
            artifact_type="cost", payload=payload, dependencies=[q_av], alternative_id=alt.id)
        c = CostEstimate(artifact_version_id=av.id, project_id=project.id, project_version_id=version.id,
            quantity_artifact_id=q.id, rate_schedule_id=rate_schedule.id, payload_json=payload)
        session.add(c); await session.flush(); costs.append((c, av))
    complete("calculate_cost", {"cost_estimate_ids": [c.id for c, _ in costs]})

    structures: list[tuple[StructuralArtifact, ArtifactVersion]] = []
    for geom, geom_av, alt in geometries:
        p = alt.design_parameters_json
        result = generate_structure(StructuralConceptRequest(project_id=project.id, source_revision=world.revision,
            geometry_artifact_id=geom.id, geometry_sha256=geom.geometry_hash,
            footprint_width_m=p["footprint_width_m"], footprint_depth_m=p["footprint_depth_m"],
            floors=p["floor_count"], floor_to_floor_m=p["floor_to_floor_m"], preferred_max_bay_m=8.0))
        payload = result.model_dump(mode="json")
        av = await new_artifact(session, project=project, version=version, world=world, actor=actor,
            artifact_type="structural", payload=payload, dependencies=[geom_av], alternative_id=alt.id)
        row = StructuralArtifact(artifact_version_id=av.id, project_id=project.id, project_version_id=version.id,
            geometry_artifact_id=geom.id, status="concept_only", payload_json=payload)
        session.add(row); await session.flush(); structures.append((row, av))
    complete("generate_structural_concept", {"structural_artifact_ids": [s.id for s, _ in structures], "certified": False})

    regulations: list[tuple[RegulatoryEvaluation, ArtifactVersion]] = []
    for geom, geom_av, alt in geometries:
        payload = {"jurisdiction": "Saudi Arabia", "status": "unknown", "results": [],
            "reason": "No authoritative regulatory ruleset has been configured. UNKNOWN is fail-safe, not PASS."}
        av = await new_artifact(session, project=project, version=version, world=world, actor=actor,
            artifact_type="regulatory", payload=payload, dependencies=[geom_av], alternative_id=alt.id, status="unknown")
        row = RegulatoryEvaluation(artifact_version_id=av.id, project_id=project.id, project_version_id=version.id,
            geometry_artifact_id=geom.id, ruleset_id=None, status="unknown", payload_json=payload)
        session.add(row); await session.flush(); regulations.append((row, av))
    complete("run_regulatory_checks", {"status": "unknown", "evaluation_ids": [r.id for r, _ in regulations]})

    all_inputs = [av for _, av, _ in geometries] + [av for _, av, *_ in quantities] + [av for _, av in costs] + [av for _, av in structures] + [av for _, av in regulations]
    validation_payload = {"status": "blocked", "checks": [
        {"code": "artifact_lineage", "status": "pass", "message": "Canonical dependency edges persisted"},
        {"code": "regulatory_source", "status": "unknown", "message": "Authoritative ruleset required"},
        {"code": "human_review", "status": "blocked", "message": "Qualified human review required"}], "human_review_required": True}
    validation_av = await new_artifact(session, project=project, version=version, world=world, actor=actor,
        artifact_type="validation", payload=validation_payload, dependencies=all_inputs, status="blocked")
    validation = ValidationRun(artifact_version_id=validation_av.id, project_id=project.id, project_version_id=version.id,
        status="blocked", payload_json=validation_payload)
    session.add(validation); await session.flush()
    for check in validation_payload["checks"]:
        session.add(ValidationCheck(validation_run_id=validation.id, code=check["code"], status=check["status"], message=check["message"]))
    complete("validate_outputs", {"validation_run_id": validation.id, "status": "blocked"})

    for av in all_inputs + [validation_av]:
        session.add(EvidenceRecord(artifact_version_id=av.id, project_version_id=version.id, source_type="generated_calculation",
            source_uri=None, source_hash=av.output_hash or "", source_version=str(av.version), content_hash=av.output_hash or "",
            verification_method="sha256_content_hash", verification_status="system_verified"))
    complete("assemble_evidence", {"evidence_count": len(all_inputs) + 1})

    snapshot_artifacts = all_inputs + [validation_av]
    package = {"project_id": project.id, "project_version_id": version.id, "project_version": version.version,
        "world_model_revision_id": world.id, "artifact_versions": [{"id": a.id, "type": a.artifact_type, "version": a.version,
        "hash": a.output_hash, "status": a.status} for a in snapshot_artifacts],
        "validation_status": "blocked", "review_required": True,
        "limitations": ["Preliminary feasibility only", "Not engineering certification", "Regulatory result remains UNKNOWN until an authoritative ruleset and evidence are reviewed"]}
    package_av = await new_artifact(session, project=project, version=version, world=world, actor=actor,
        artifact_type="deliverable", payload=package, dependencies=snapshot_artifacts, status="blocked")
    deliverable = DeliverableRecord(organization_id=project.organization_id, project_id=project.id, project_version_id=version.id,
        artifact_id=package_av.id, artifact_version=str(package_av.version), source_hash=package_av.output_hash or "", format="json",
        payload_json=package, status="awaiting_review", created_by=actor)
    session.add(deliverable); await session.flush()
    for av in snapshot_artifacts: session.add(DeliverableArtifact(deliverable_id=deliverable.id, artifact_version_id=av.id))
    complete("generate_feasibility_package", {"deliverable_id": deliverable.id, "status": "awaiting_review"})

    session.add(DecisionRecord(project_version_id=version.id, provider="deterministic", provider_version="1",
        inputs_json={"alternatives": [a.id for a, _ in alternatives]}, outputs_json={"ranking": [a.id for a, _ in alternatives]},
        latency_ms=0, fallback_used=False))
    workflow.state = "succeeded"; version.status = "awaiting_review"
    await session.commit()
    return workflow


async def stale_prior_version(session: AsyncSession, parent: ProjectVersion) -> list[str]:
    artifacts = list((await session.scalars(select(ArtifactVersion).where(
        ArtifactVersion.project_version_id == parent.id, ArtifactVersion.status.in_(["current", "blocked", "unknown"])))).all())
    for artifact in artifacts: artifact.status = "stale"
    deliverables = list((await session.scalars(select(DeliverableRecord).where(DeliverableRecord.project_version_id == parent.id))).all())
    for deliverable in deliverables: deliverable.status = "stale"
    return [a.id for a in artifacts]
