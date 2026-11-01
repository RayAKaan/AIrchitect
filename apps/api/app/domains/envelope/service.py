from __future__ import annotations

import math

from pyproj import CRS, Transformer
from shapely.geometry import shape, mapping
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ArtifactVersion, Project, ProjectVersion, User, WorldModelRevision
from app.db.site_models import SiteRevision
from app.domains.foundation.service import error, resolve_project_version, resolve_world_model
from app.domains.lifecycle.service import canonical_hash, new_artifact
from .schemas import PlanningRule


def _projected_transformer(boundary):
    coords = boundary["coordinates"][0]
    lon = sum(p[0] for p in coords[:-1]) / max(1, len(coords)-1)
    lat = sum(p[1] for p in coords[:-1]) / max(1, len(coords)-1)
    local = CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs")
    return Transformer.from_crs("EPSG:4326", local, always_xy=True), Transformer.from_crs(local, "EPSG:4326", always_xy=True)


def _rule(rule):
    return None if rule is None or rule.value is None else float(rule.value)




def effective_envelope_request(body, world):
    """Use a canonical user design parameter when present, never as verified regulation."""
    properties = world.model_json.get("properties") or {}
    raw_setback = properties.get("setback_m")
    if raw_setback is None:
        return body
    if isinstance(raw_setback, dict):
        raw_setback = raw_setback.get("value")
    try:
        setback = float(raw_setback)
    except (TypeError, ValueError):
        raise error(409, "CANONICAL_SETBACK_INVALID", "The canonical setback design parameter is invalid") from None
    if not math.isfinite(setback) or setback < 0:
        raise error(409, "CANONICAL_SETBACK_INVALID", "The canonical setback design parameter must be finite and non-negative")
    return body.model_copy(update={
        "setback_m": PlanningRule(
            value=setback,
            unit="m",
            source="USER_DESIGN_PARAMETER",
            status="DESIGN_PARAMETER",
            applicability="User-authored design parameter; not verified planning regulation",
        )
    })


def build_envelope(boundary: dict, request) -> dict:
    source = shape(boundary)
    if source.geom_type != "Polygon" or not source.is_valid:
        raise error(422, "INVALID_SITE_GEOMETRY", "A valid Polygon site boundary is required")
    forward, inverse = _projected_transformer(boundary)
    local = __import__("shapely.ops", fromlist=["transform"]).transform(forward.transform, source)
    setback = _rule(request.setback_m)
    if setback is not None and setback < 0: raise error(422, "INVALID_SETBACK", "Setback cannot be negative")
    buildable = local.buffer(-setback) if setback else local
    if buildable.is_empty or buildable.area <= 0:
        raise error(409, "NO_BUILDABLE_AREA", "Setbacks eliminate the buildable site area")
    site_area = local.area
    footprint_limit = site_area * _rule(request.max_coverage) if _rule(request.max_coverage) is not None else None
    far_limit = site_area * _rule(request.far) if _rule(request.far) is not None else None
    max_gfa = min(x for x in (footprint_limit, far_limit) if x is not None) if any(x is not None for x in (footprint_limit, far_limit)) else None
    violations=[]; unknowns=[]
    if request.max_coverage is None: unknowns.append("max_coverage")
    if request.far is None: unknowns.append("far")
    if request.max_height_m is None: unknowns.append("max_height_m")
    if max_gfa is not None and max_gfa > buildable.area:
        violations.append({"code":"FAR_OR_COVERAGE_EXCEEDS_BUILDABLE_AREA","severity":"INFO","message":"Area limit exceeds the setback-derived footprint; buildable polygon remains the controlling footprint."})
    payload = {"schema_version":"s2-envelope-v1","site_area_m2":round(site_area,3),"buildable_area_m2":round(buildable.area,3),
        "buildable_polygon":mapping(__import__("shapely.ops", fromlist=["transform"]).transform(inverse.transform, buildable)),
        "setback_m":setback,"max_coverage":_rule(request.max_coverage),"far":_rule(request.far),
        "max_height_m":_rule(request.max_height_m),"max_footprint_m2":None if footprint_limit is None else round(footprint_limit,3),
        "max_gfa_m2":None if max_gfa is None else round(max_gfa,3),"violations":violations,"unknowns":sorted(unknowns),
        "planning_evidence":{"setback":request.setback_m.model_dump(),
            "max_coverage":request.max_coverage.model_dump() if request.max_coverage else None,
            "far":request.far.model_dump() if request.far else None,
            "max_height_m":request.max_height_m.model_dump() if request.max_height_m else None}}
    payload["envelope_hash"] = canonical_hash(payload)
    return payload

async def generate(session: AsyncSession, project_id: str, version_ref: str, body, user: User) -> dict:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    world = await resolve_world_model(session, version.id)
    site_revision = await session.scalar(select(SiteRevision).where(SiteRevision.project_version_id == version.id)
        .order_by(SiteRevision.revision.desc()).limit(1))
    if site_revision is None:
        raise error(409, "SITE_REQUIRED", "Set and commit a canonical site boundary before envelope generation")
    effective_body = effective_envelope_request(body, world)
    payload = build_envelope(site_revision.boundary_geojson, effective_body)
    payload["source_lineage"] = {
        "site_revision_id": site_revision.id,
        "site_revision_number": site_revision.revision,
        "site_revision_hash": site_revision.content_hash,
        "world_model_revision_id": world.id,
        "world_model_hash": world.model_hash,
    }
    payload["envelope_hash"] = canonical_hash({
        key: value for key, value in payload.items() if key != "envelope_hash"
    })
    previous = await session.scalar(select(ArtifactVersion).where(ArtifactVersion.project_version_id == version.id,
        ArtifactVersion.artifact_type == "planning_envelope").order_by(ArtifactVersion.version.desc()).limit(1))
    if previous and previous.output_hash == payload["envelope_hash"]:
        return {"artifact_id":previous.id,"envelope":previous.payload_json,"envelope_hash":payload["envelope_hash"],"idempotent":True}
    artifact = await new_artifact(session, project=project, version=version, world=world, actor=user.id,
        artifact_type="planning_envelope", payload=payload, status="current")
    artifact.output_hash=payload["envelope_hash"]
    await session.commit()
    return {"artifact_id":artifact.id,"envelope":payload,"envelope_hash":payload["envelope_hash"],"idempotent":False}
