from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context
from pydantic import AnyHttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.security import read_token
from app.db.models import (\n    ArtifactDependency, ArtifactVersion, AssumptionRecord, BuildingBriefRecord,\n    DesignAlternative, GeometryArtifact, RequirementRecord,\n)\nfrom app.db.site_models import (\n    SiteConstraint, SiteEvidence, SiteLayerSnapshot, SiteObservation, SiteRevision, SiteSource,\n)
from app.db.session import get_engine
from app.domains.commands.preview import preview_command
from app.domains.commands.schemas import CommandEnvelope
from app.domains.foundation.service import resolve_project_version, resolve_world_model
from app.domains.lifecycle.service import canonical_hash

MCP_RESOURCE = settings.mcp_server_url


class SessionTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            user_id = read_token(token)
        except Exception:
            return None
        return AccessToken(
            token=token,
            client_id=user_id,
            scopes=["airchitect:read", "airchitect:write"],
            resource=MCP_RESOURCE,
        )


mcp = MCPServer(
    "AIrchitect",
    version="1.0.0",
    instructions=(
        "AIrchitect is the canonical architectural system. Read project state before proposing changes. "
        "Tools in this bridge never mutate canonical state. Treat engineering and regulatory outputs as "
        "screening/decision support, not certification."
    ),
    token_verifier=SessionTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(MCP_RESOURCE),
        resource_server_url=AnyHttpUrl(MCP_RESOURCE),
        required_scopes=["airchitect:read"],
        validate_token_resource=True,
    ),
)


def _session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def _session() -> Any:
    async with _session_factory()() as session:
        yield session


def _caller(ctx: Context) -> str:
    access = get_access_token()
    if access is None or not access.client_id:
        raise PermissionError("MCP authentication required")
    return access.client_id


async def _version_context(session: AsyncSession, project_id: str, version_id: str, user_id: str):
    project, version = await resolve_project_version(session, project_id, version_id, user_id)
    world = await resolve_world_model(session, version.id)
    return project, version, world


@mcp.tool()
async def get_project_context(project_id: str, version_id: str, ctx: Context) -> dict[str, Any]:
    """Read the authoritative project brief, requirements, assumptions, and World Model revision."""
    user_id = _caller(ctx)
    async with _session() as session:
        project, version, world = await _version_context(session, project_id, version_id, user_id)
        brief = await session.scalar(
            select(BuildingBriefRecord)
            .where(BuildingBriefRecord.project_version_id == version.id)
            .order_by(BuildingBriefRecord.revision.desc())
        )
        requirements = (
            await session.scalars(
                select(RequirementRecord)
                .where(RequirementRecord.project_version_id == version.id)
                .order_by(RequirementRecord.created_at, RequirementRecord.id)
            )
        ).all()
        assumptions = (
            await session.scalars(
                select(AssumptionRecord)
                .where(AssumptionRecord.project_version_id == version.id)
                .order_by(AssumptionRecord.created_at, AssumptionRecord.id)
            )
        ).all()
        return {
            "project": {"id": project.id, "name": project.name, "building_type": project.building_type, "location": project.location},
            "version": {"id": version.id, "label": f"V{version.version}", "status": version.status, "revision": version.revision_number},
            "brief": None if brief is None else {"revision": brief.revision, "text": brief.raw_text, "hash": brief.content_hash},
            "requirements": [
                {"parameter": row.parameter, "category": row.category, "value": row.normalized_value_json, "unit": row.unit, "status": row.status, "confidence": row.confidence}
                for row in requirements
            ],
            "assumptions": [
                {"parameter": row.parameter, "value": row.value_json.get("value"), "unit": row.unit, "status": row.status, "reason": row.reason}
                for row in assumptions
            ],
            "world_model": world.model_json,
            "world_model_hash": world.model_hash,
            "world_model_revision": world.revision,
        }


@mcp.tool()
async def preview_intent(text: str, project_id: str, version_id: str, ctx: Context) -> dict[str, Any]:
    """Interpret natural-language design intent without mutating canonical state."""
    user_id = _caller(ctx)
    async with _session() as session:
        from app.domains.commands.intent_contract import contract_for
        from app.domains.commands.intent_parser import parse_intent
        from app.domains.commands.target_resolution import resolve_target
        from app.domains.semantic_model.editing import load_editable_model

        proposal = parse_intent(text)
        payload = dict(proposal.payload)
        revision_hash = None
        expected_types = {"MoveBuilding": "Building", "RotateBuilding": "Building", "ResizeSpace": "Space", "MoveSpace": "Space"}
        if proposal.command_type in expected_types:
            user = await session.get(__import__("app.db.models", fromlist=["User"]).User, user_id)
            if user is None:
                raise PermissionError("MCP user no longer exists")
            _, _, world, model, _ = await load_editable_model(session, project_id, version_id, user)
            revision_hash = world.model_hash
            target_name = payload.get("target_name")
            if isinstance(target_name, str) and "element_id" not in payload:
                resolution = resolve_target(model, name=target_name, expected_type=expected_types[proposal.command_type])
                if resolution.element_id is not None and not resolution.ambiguous:
                    payload["element_id"] = resolution.element_id
        proposal = proposal.__class__(proposal.command_type, payload, proposal.confidence, proposal.missing_fields, proposal.ambiguous)
        contract = contract_for(proposal)
        return {
            "command_type": contract.command_type,
            "payload": contract.payload,
            "confidence": proposal.confidence,
            "missing_fields": list(contract.missing_fields),
            "ambiguous": proposal.ambiguous,
            "executable": contract.executable,
            "reason": contract.reason,
            "base_revision_hash": revision_hash,
        }


@mcp.tool()
async def preview_change(
    command_id: str,
    command_type: str,
    project_id: str,
    version_id: str,
    base_revision_hash: str,
    payload: dict[str, Any],
    reason: str,
    ctx: Context,
) -> dict[str, Any]:
    """Validate a proposed canonical change and return its deterministic impact; never commits."""
    _caller(ctx)
    envelope = CommandEnvelope(
        command_id=command_id,
        type=command_type,
        schema_version=1,
        project_id=project_id,
        version_id=version_id,
        base_revision_hash=base_revision_hash,
        idempotency_key=canonical_hash({"command_id": command_id, "payload": payload})[:32],
        payload=payload,
        mode="preview",
        reason=reason,
    )
    return preview_command(envelope).model_dump(mode="json")



@mcp.tool()
async def get_site_context(project_id: str, version_id: str, ctx: Context) -> dict[str, Any]:
    """Read the latest canonical site revision and its evidence-backed analysis projections."""
    user_id = _caller(ctx)
    async with _session() as session:
        project, version, _world = await _version_context(session, project_id, version_id, user_id)
        revision = await session.scalar(
            select(SiteRevision)
            .where(SiteRevision.project_id == project.id, SiteRevision.project_version_id == version.id)
            .order_by(SiteRevision.revision.desc())
            .limit(1)
        )
        if revision is None:
            return {"available": False, "reason": "No validated site boundary exists for this project version."}
        layers = (
            await session.scalars(
                select(SiteLayerSnapshot)
                .where(SiteLayerSnapshot.site_revision_id == revision.id)
                .order_by(SiteLayerSnapshot.layer_type, SiteLayerSnapshot.created_at.desc())
            )
        ).all()
        constraints = (
            await session.scalars(
                select(SiteConstraint)
                .where(SiteConstraint.site_revision_id == revision.id)
                .order_by(SiteConstraint.constraint_type, SiteConstraint.id)
                .limit(100)
            )
        ).all()
        observations = (
            await session.scalars(
                select(SiteObservation)
                .where(SiteObservation.site_revision_id == revision.id)
                .order_by(SiteObservation.observation_type, SiteObservation.id)
                .limit(100)
            )
        ).all()
        evidence = (
            await session.scalars(
                select(SiteEvidence)
                .where(SiteEvidence.site_revision_id == revision.id)
                .order_by(SiteEvidence.claim_type, SiteEvidence.id)
                .limit(100)
            )
        ).all()
        sources = (
            await session.scalars(
                select(SiteSource)
                .where(SiteSource.site_revision_id == revision.id)
                .order_by(SiteSource.provider, SiteSource.dataset)
                .limit(100)
            )
        ).all()
        return {
            "available": True,
            "project_id": project.id,
            "project_version_id": version.id,
            "revision": revision.revision,
            "revision_id": revision.id,
            "content_hash": revision.content_hash,
            "boundary": revision.boundary_geojson,
            "boundary_crs": revision.boundary_crs,
            "calculation_crs": revision.calculation_crs,
            "area_m2": revision.area_m2,
            "perimeter_m": revision.perimeter_m,
            "validation": revision.validation_json,
            "layers": [
                {"type": row.layer_type, "status": row.status, "provider": row.provider,
                 "dataset_version": row.dataset_version, "payload": row.payload_json}
                for row in layers
            ],
            "constraints": [
                {"type": row.constraint_type, "status": row.status, "value": row.value_json,
                 "geometry": row.geometry_geojson, "evidence_id": row.evidence_id}
                for row in constraints
            ],
            "observations": [
                {"type": row.observation_type, "status": row.status, "value": row.value_json,
                 "geometry": row.geometry_geojson, "evidence_id": row.evidence_id}
                for row in observations
            ],
            "evidence": [
                {"id": row.id, "claim_type": row.claim_type, "status": row.status,
                 "value": row.value_json, "confidence": row.confidence, "method": row.method,
                 "source_id": row.source_id}
                for row in evidence
            ],
            "sources": [
                {"provider": row.provider, "dataset": row.dataset, "dataset_version": row.dataset_version,
                 "source_url": row.source_url, "retrieved_at": row.retrieval_time.isoformat(),
                 "license": row.license, "attribution": row.attribution, "geographic_scope": row.geographic_scope}
                for row in sources
            ],
            "canonical_state_mutated": False,
        }


@mcp.tool()
async def list_design_alternatives(project_id: str, version_id: str, ctx: Context) -> dict[str, Any]:
    """List design alternatives and their geometry availability without selecting or changing them."""
    user_id = _caller(ctx)
    async with _session() as session:
        project, version, world = await _version_context(session, project_id, version_id, user_id)
        alternatives = (
            await session.scalars(
                select(DesignAlternative)
                .where(DesignAlternative.project_id == project.id, DesignAlternative.project_version_id == version.id)
                .order_by(DesignAlternative.created_at, DesignAlternative.id)
                .limit(100)
            )
        ).all()
        geometries = (
            await session.scalars(
                select(GeometryArtifact)
                .where(GeometryArtifact.project_id == project.id,
                       GeometryArtifact.project_version_id == version.id,
                       GeometryArtifact.source == "CAD_BREP")
                .order_by(GeometryArtifact.created_at.desc())
            )
        ).all()
        geometry_by_alternative = {}
        for geometry in geometries:
            geometry_by_alternative.setdefault(geometry.alternative_id, geometry)
        return {
            "project_id": project.id,
            "project_version_id": version.id,
            "world_model_hash": world.model_hash,
            "alternatives": [
                {
                    "id": row.id,
                    "name": row.name,
                    "description": row.description,
                    "status": row.status,
                    "strategy_id": row.strategy_id,
                    "metrics": row.key_metrics_json,
                    "constraints": row.constraint_results_json,
                    "assumptions": row.assumptions_json,
                    "unknowns": row.unknowns_json,
                    "tradeoffs": row.tradeoffs_json,
                    "design_hash": row.design_hash,
                    "input_world_model_hash": row.input_world_model_hash,
                    "geometry_available": row.id in geometry_by_alternative,
                    "geometry_status": geometry_by_alternative[row.id].status if row.id in geometry_by_alternative else None,
                }
                for row in alternatives
            ],
            "canonical_state_mutated": False,
            "notice": "Alternatives are proposals. Human selection and downstream validation remain separate actions.",
        }


@mcp.tool()
async def list_project_artifacts(project_id: str, version_id: str, ctx: Context) -> dict[str, Any]:
    """List versioned project deliverables, freshness status and dependency lineage."""
    user_id = _caller(ctx)
    async with _session() as session:
        project, version, world = await _version_context(session, project_id, version_id, user_id)
        artifacts = (
            await session.scalars(
                select(ArtifactVersion)
                .where(ArtifactVersion.project_id == project.id, ArtifactVersion.project_version_id == version.id)
                .order_by(ArtifactVersion.created_at.desc(), ArtifactVersion.id)
                .limit(200)
            )
        ).all()
        artifact_ids = [row.id for row in artifacts]
        dependencies = []
        if artifact_ids:
            dependencies = (
                await session.scalars(
                    select(ArtifactDependency).where(ArtifactDependency.artifact_version_id.in_(artifact_ids))
                )
            ).all()
        dependency_map: dict[str, list[str]] = {}
        for dependency in dependencies:
            dependency_map.setdefault(dependency.artifact_version_id, []).append(dependency.depends_on_artifact_version_id)
        return {
            "project_id": project.id,
            "project_version_id": version.id,
            "world_model_hash": world.model_hash,
            "artifacts": [
                {
                    "id": row.id,
                    "type": row.artifact_type,
                    "version": row.version,
                    "status": row.status,
                    "output_hash": row.output_hash,
                    "provenance": row.provenance_json,
                    "input_references": row.input_references_json,
                    "depends_on": sorted(dependency_map.get(row.id, [])),
                    "created_at": row.created_at.isoformat(),
                }
                for row in artifacts
            ],
            "canonical_state_mutated": False,
        }


mcp_app = mcp.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    host="127.0.0.1",
)
