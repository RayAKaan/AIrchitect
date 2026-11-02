from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactVersion, DesignAlternative, User
from app.db.site_models import SiteRevision
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.design.lineage import alternative_is_stale, current_design_input_lineage
from app.domains.design.s2_inputs import S2DesignInputError, resolve_s2_design_inputs
from app.domains.foundation.service import audit, error, resolve_project_version, resolve_world_model
from app.domains.lifecycle.service import new_artifact

from .architectural_elements import ArchitecturalElementError, compile_architectural_elements
from .service import SpatialLayoutError, build_spatial_layout
from .topology import SpatialTopologyError, build_spatial_topology


router = APIRouter(tags=["spatial-layout"])


async def _current_artifact(session: AsyncSession, version_id: str, artifact_type: str) -> ArtifactVersion:
    row = await session.scalar(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.project_version_id == version_id,
            ArtifactVersion.artifact_type == artifact_type,
            ArtifactVersion.status == "current",
        )
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
    )
    if row is None or not row.output_hash:
        raise error(
            409,
            f"{artifact_type.upper()}_REQUIRED",
            f"A current {artifact_type.replace('_', ' ')} artifact is required before spatial layout generation",
        )
    return row


async def _layout_is_current(
    session: AsyncSession,
    version_id: str,
    world_hash: str,
    artifact: ArtifactVersion,
) -> bool:
    source = artifact.payload_json.get("source_lineage") or {}
    envelope_lineage = source.get("envelope_source_lineage") or {}
    current_lineage = await current_design_input_lineage(session, version_id)
    site_revision = await session.scalar(
        select(SiteRevision)
        .where(SiteRevision.project_version_id == version_id)
        .order_by(SiteRevision.revision.desc())
        .limit(1)
    )
    selected_alternative = await session.scalar(
        select(DesignAlternative).where(
            DesignAlternative.project_version_id == version_id,
            DesignAlternative.status == "SELECTED",
        )
    )
    return (
        artifact.status == "current"
        and source.get("world_model_hash") == world_hash
        and source.get("program_hash") == current_lineage.get("program")
        and source.get("envelope_hash") == current_lineage.get("envelope")
        and site_revision is not None
        and envelope_lineage.get("site_revision_id") == site_revision.id
        and envelope_lineage.get("site_revision_hash") == site_revision.content_hash
        and selected_alternative is not None
        and selected_alternative.id == source.get("alternative_id")
        and not alternative_is_stale(selected_alternative, world_hash, current_lineage)
    )


@router.post("/projects/{project_id}/versions/{version_ref}/spatial-layout/generate", status_code=201)
async def generate_spatial_layout(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    if version.status != "COMMITTED":
        raise error(
            409,
            "WORLD_MODEL_INVALID",
            "Commit the canonical project version before spatial layout generation",
            version_status=version.status,
        )
    world = await resolve_world_model(session, version.id)
    program = await _current_artifact(session, version.id, "architectural_program")
    envelope = await _current_artifact(session, version.id, "planning_envelope")
    site_revision = await session.scalar(
        select(SiteRevision)
        .where(SiteRevision.project_version_id == version.id)
        .order_by(SiteRevision.revision.desc())
        .limit(1)
    )
    envelope_lineage = envelope.payload_json.get("source_lineage") or {}
    if (
        site_revision is None
        or envelope_lineage.get("site_revision_id") != site_revision.id
        or envelope_lineage.get("site_revision_hash") != site_revision.content_hash
    ):
        raise error(
            409,
            "STALE_ENVELOPE",
            "The planning envelope does not match the latest canonical site boundary; regenerate the envelope first",
            current_site_revision_id=site_revision.id if site_revision else None,
            envelope_site_revision_id=envelope_lineage.get("site_revision_id"),
        )

    try:
        resolve_s2_design_inputs(
            program.payload_json,
            envelope.payload_json,
            world_hash=world.model_hash or "",
        )
    except S2DesignInputError as exc:
        raise error(409, exc.code, str(exc), **exc.context) from exc

    lineage = await current_design_input_lineage(session, version.id)
    alternative = await session.scalar(
        select(DesignAlternative).where(
            DesignAlternative.project_id == project.id,
            DesignAlternative.project_version_id == version.id,
            DesignAlternative.status == "SELECTED",
        )
    )
    if alternative is None:
        raise error(
            409,
            "SELECTED_ALTERNATIVE_REQUIRED",
            "Select a current design alternative before generating a spatial layout",
        )
    if alternative_is_stale(alternative, world.model_hash or "", lineage):
        raise error(
            409,
            "STALE_ARTIFACT",
            "The selected alternative does not match the current World Model, programme and envelope",
            current_world_model_hash=world.model_hash,
            current_input_lineage=lineage,
            alternative_input_lineage=(alternative.provenance_json or {}).get("input_lineage", {}),
        )
    alternative_artifact = await session.get(ArtifactVersion, alternative.artifact_version_id)
    if alternative_artifact is None or alternative_artifact.status != "current":
        raise error(409, "STALE_ARTIFACT", "The selected alternative artifact is not current")

    metrics = dict(alternative.key_metrics_json or {})
    metrics["design_hash"] = alternative.design_hash
    try:
        payload = build_spatial_layout(
            project_id=project.id,
            project_version_id=version.id,
            world_model_hash=world.model_hash or "",
            program=program.payload_json,
            envelope=envelope.payload_json,
            alternative_id=alternative.id,
            design_parameters=alternative.design_parameters_json or {},
            design_metrics=metrics,
        )
    except SpatialLayoutError as exc:
        raise error(409, exc.code, str(exc), **exc.context) from exc

    digest = payload["layout_hash"]
    existing = await session.scalar(
        select(ArtifactVersion).where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "spatial_layout",
            ArtifactVersion.output_hash == digest,
            ArtifactVersion.status == "current",
        )
    )
    if existing is not None:
        return {
            "artifact_id": existing.id,
            "artifact_version": existing.version,
            "layout_hash": digest,
            "layout": existing.payload_json,
            "idempotent": True,
        }

    previous = list(
        (
            await session.scalars(
                select(ArtifactVersion).where(
                    ArtifactVersion.project_version_id == version.id,
                    ArtifactVersion.artifact_type == "spatial_layout",
                    ArtifactVersion.status == "current",
                )
            )
        ).all()
    )
    for row in previous:
        row.status = "stale"

    artifact = await new_artifact(
        session,
        project=project,
        version=version,
        world=world,
        actor=user.id,
        artifact_type="spatial_layout",
        payload=payload,
        dependencies=[program, envelope, alternative_artifact],
        alternative_id=alternative.id,
        status="current",
    )
    artifact.output_hash = digest
    await audit(
        session,
        project=project,
        version=version,
        actor=user.id,
        action="SPATIAL_LAYOUT_GENERATED",
        entity="artifact_version",
        entity_id=artifact.id,
        metadata={
            "layout_hash": digest,
            "selected_alternative_id": alternative.id,
            "world_model_hash": world.model_hash,
            "program_hash": program.output_hash,
            "envelope_hash": envelope.output_hash,
            "space_count": len(payload["spaces"]),
            "floor_count": len(payload["floor_plates"]),
            "status": payload["status"],
        },
    )
    await session.commit()
    return {
        "artifact_id": artifact.id,
        "artifact_version": artifact.version,
        "layout_hash": digest,
        "layout": payload,
        "idempotent": False,
    }


@router.get("/projects/{project_id}/versions/{version_ref}/spatial-layout")
async def get_spatial_layout(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    artifact = await session.scalar(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "spatial_layout",
        )
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
    )
    if artifact is None:
        raise error(404, "SPATIAL_LAYOUT_NOT_FOUND", "No spatial layout has been generated for this project version")
    stale = not await _layout_is_current(session, version.id, world.model_hash or "", artifact)
    return {
        "artifact_id": artifact.id,
        "artifact_version": artifact.version,
        "layout_hash": artifact.output_hash,
        "status": "STALE" if stale else artifact.payload_json.get("status", "PRELIMINARY"),
        "layout": artifact.payload_json,
    }


@router.post("/projects/{project_id}/versions/{version_ref}/spatial-topology/generate", status_code=201)
async def generate_spatial_topology(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    if version.status != "COMMITTED":
        raise error(
            409,
            "WORLD_MODEL_INVALID",
            "Commit the canonical project version before spatial topology generation",
            version_status=version.status,
        )
    world = await resolve_world_model(session, version.id)
    layout_artifact = await _current_artifact(session, version.id, "spatial_layout")
    if not await _layout_is_current(session, version.id, world.model_hash or "", layout_artifact):
        raise error(
            409,
            "STALE_SPATIAL_LAYOUT",
            "Regenerate the spatial layout from the current World Model, programme, "
            "envelope, site and selected concept",
        )
    try:
        payload = build_spatial_topology(layout_artifact.payload_json)
    except SpatialTopologyError as exc:
        raise error(409, exc.code, str(exc), **exc.context) from exc

    digest = payload["topology_hash"]
    existing = await session.scalar(
        select(ArtifactVersion).where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "spatial_topology",
            ArtifactVersion.output_hash == digest,
            ArtifactVersion.status == "current",
        )
    )
    if existing is not None:
        return {
            "artifact_id": existing.id,
            "artifact_version": existing.version,
            "topology_hash": digest,
            "topology": existing.payload_json,
            "idempotent": True,
        }

    previous = list(
        (
            await session.scalars(
                select(ArtifactVersion).where(
                    ArtifactVersion.project_version_id == version.id,
                    ArtifactVersion.artifact_type == "spatial_topology",
                    ArtifactVersion.status == "current",
                )
            )
        ).all()
    )
    for row in previous:
        row.status = "stale"

    artifact = await new_artifact(
        session,
        project=project,
        version=version,
        world=world,
        actor=user.id,
        artifact_type="spatial_topology",
        payload=payload,
        dependencies=[layout_artifact],
        alternative_id=layout_artifact.alternative_id,
        status="current",
    )
    artifact.output_hash = digest
    await audit(
        session,
        project=project,
        version=version,
        actor=user.id,
        action="SPATIAL_TOPOLOGY_GENERATED",
        entity="artifact_version",
        entity_id=artifact.id,
        metadata={
            "topology_hash": digest,
            "layout_artifact_id": layout_artifact.id,
            "layout_hash": layout_artifact.output_hash,
            "world_model_hash": world.model_hash,
            "node_count": len(payload["nodes"]),
            "edge_count": len(payload["edges"]),
            "status": payload["status"],
        },
    )
    await session.commit()
    return {
        "artifact_id": artifact.id,
        "artifact_version": artifact.version,
        "topology_hash": digest,
        "topology": payload,
        "idempotent": False,
    }


@router.get("/projects/{project_id}/versions/{version_ref}/spatial-topology")
async def get_spatial_topology(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    artifact = await session.scalar(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "spatial_topology",
        )
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
    )
    if artifact is None:
        raise error(
            404,
            "SPATIAL_TOPOLOGY_NOT_FOUND",
            "No spatial topology has been generated for this project version",
        )
    current_layout = await session.scalar(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "spatial_layout",
            ArtifactVersion.status == "current",
        )
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
    )
    layout_current = (
        current_layout is not None
        and await _layout_is_current(session, version.id, world.model_hash or "", current_layout)
    )
    source = artifact.payload_json.get("source_lineage") or {}
    stale = (
        artifact.status != "current"
        or not layout_current
        or current_layout is None
        or source.get("world_model_hash") != world.model_hash
        or source.get("layout_hash") != current_layout.payload_json.get("layout_hash")
    )
    return {
        "artifact_id": artifact.id,
        "artifact_version": artifact.version,
        "topology_hash": artifact.output_hash,
        "status": "STALE" if stale else artifact.payload_json.get("status", "REVIEW_REQUIRED"),
        "topology": artifact.payload_json,
    }


@router.post("/projects/{project_id}/versions/{version_ref}/architectural-elements/generate", status_code=201)
async def generate_architectural_elements(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Create a reviewable element proposal artifact from current layout and topology."""
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    if version.status != "COMMITTED":
        raise error(
            409,
            "WORLD_MODEL_INVALID",
            "Commit the canonical project version before architectural element proposal generation",
            version_status=version.status,
        )
    world = await resolve_world_model(session, version.id)
    layout_artifact = await _current_artifact(session, version.id, "spatial_layout")
    if not await _layout_is_current(session, version.id, world.model_hash or "", layout_artifact):
        raise error(
            409,
            "STALE_SPATIAL_LAYOUT",
            "Regenerate the spatial layout from the current World Model, programme, envelope, "
            "site and selected concept",
        )
    topology_artifact = await _current_artifact(session, version.id, "spatial_topology")
    topology_source = topology_artifact.payload_json.get("source_lineage") or {}
    if (
        topology_source.get("world_model_hash") != world.model_hash
        or topology_source.get("layout_hash") != layout_artifact.output_hash
    ):
        raise error(
            409,
            "STALE_SPATIAL_TOPOLOGY",
            "Regenerate spatial topology from the current spatial layout before deriving architectural elements",
        )
    try:
        payload = compile_architectural_elements(
            layout_artifact.payload_json,
            topology_artifact.payload_json,
        )
    except ArchitecturalElementError as exc:
        raise error(409, exc.code, str(exc), **exc.context) from exc

    digest = payload["elements_hash"]
    existing = await session.scalar(
        select(ArtifactVersion).where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "architectural_elements",
            ArtifactVersion.output_hash == digest,
            ArtifactVersion.status == "current",
        )
    )
    if existing is not None:
        return {
            "artifact_id": existing.id,
            "artifact_version": existing.version,
            "elements_hash": digest,
            "elements": existing.payload_json,
            "idempotent": True,
        }

    previous = list(
        (
            await session.scalars(
                select(ArtifactVersion).where(
                    ArtifactVersion.project_version_id == version.id,
                    ArtifactVersion.artifact_type == "architectural_elements",
                    ArtifactVersion.status == "current",
                )
            )
        ).all()
    )
    for row in previous:
        row.status = "stale"

    artifact = await new_artifact(
        session,
        project=project,
        version=version,
        world=world,
        actor=user.id,
        artifact_type="architectural_elements",
        payload=payload,
        dependencies=[layout_artifact, topology_artifact],
        alternative_id=layout_artifact.alternative_id,
        status="current",
    )
    artifact.output_hash = digest
    await audit(
        session,
        project=project,
        version=version,
        actor=user.id,
        action="ARCHITECTURAL_ELEMENTS_PROPOSED",
        entity="artifact_version",
        entity_id=artifact.id,
        metadata={
            "elements_hash": digest,
            "layout_hash": layout_artifact.output_hash,
            "topology_hash": topology_artifact.output_hash,
            "world_model_hash": world.model_hash,
            "candidate_count": len(payload["candidates"]),
            "status": payload["status"],
        },
    )
    await session.commit()
    return {
        "artifact_id": artifact.id,
        "artifact_version": artifact.version,
        "elements_hash": digest,
        "elements": payload,
        "idempotent": False,
    }


@router.get("/projects/{project_id}/versions/{version_ref}/architectural-elements")
async def get_architectural_elements(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    artifact = await session.scalar(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "architectural_elements",
        )
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
    )
    if artifact is None:
        raise error(
            404,
            "ARCHITECTURAL_ELEMENTS_NOT_FOUND",
            "No architectural element proposal has been generated for this project version",
        )
    layout_artifact = await session.scalar(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "spatial_layout",
            ArtifactVersion.status == "current",
        )
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
    )
    topology_artifact = await session.scalar(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.project_version_id == version.id,
            ArtifactVersion.artifact_type == "spatial_topology",
            ArtifactVersion.status == "current",
        )
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
    )
    layout_current = (
        layout_artifact is not None
        and await _layout_is_current(session, version.id, world.model_hash or "", layout_artifact)
    )
    source = artifact.payload_json.get("source_lineage") or {}
    topology_source = topology_artifact.payload_json.get("source_lineage") if topology_artifact else {}
    stale = (
        artifact.status != "current"
        or not layout_current
        or layout_artifact is None
        or topology_artifact is None
        or topology_artifact.status != "current"
        or source.get("world_model_hash") != world.model_hash
        or source.get("layout_hash") != (layout_artifact.output_hash if layout_artifact else None)
        or source.get("topology_hash") != (topology_artifact.output_hash if topology_artifact else None)
        or topology_source.get("layout_hash") != (layout_artifact.output_hash if layout_artifact else None)
        or topology_source.get("world_model_hash") != world.model_hash
    )
    return {
        "artifact_id": artifact.id,
        "artifact_version": artifact.version,
        "elements_hash": artifact.output_hash,
        "status": "STALE" if stale else artifact.payload_json.get("status", "REVIEW_REQUIRED"),
        "elements": artifact.payload_json,
    }
