from __future__ import annotations

import math

from pyproj import CRS, Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform as transform_geometry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ArtifactVersion, Project, ProjectVersion, User, WorldModelRevision
from app.db.site_models import SiteRevision
from app.domains.foundation.service import error, resolve_project_version, resolve_world_model
from app.domains.lifecycle.service import canonical_hash, new_artifact
from .schemas import PlanningRule


USABLE_RULE_STATUSES = {"VERIFIED", "CONFIRMED", "DESIGN_PARAMETER"}


def _projected_transformer(boundary):
    source = shape(boundary)
    if source.is_empty:
        raise error(422, "INVALID_SITE_GEOMETRY", "A non-empty Polygon site boundary is required")
    center = source.centroid
    local = CRS.from_proj4(
        f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m +no_defs"
    )
    return (
        Transformer.from_crs("EPSG:4326", local, always_xy=True),
        Transformer.from_crs(local, "EPSG:4326", always_xy=True),
    )


def _rule(rule):
    if rule is None or rule.value is None:
        return None
    status = str(getattr(rule, "status", "UNKNOWN")).upper()
    if status not in USABLE_RULE_STATUSES:
        return None
    value = float(rule.value)
    if not math.isfinite(value):
        raise error(422, "INVALID_PLANNING_VALUE", "Planning parameters must be finite numbers")
    return value


def _validated_rule(rule, *, name: str, unit: str, minimum: float, maximum: float | None = None):
    value = _rule(rule)
    if value is None:
        return None
    if getattr(rule, "unit", None) != unit:
        raise error(
            422,
            "PLANNING_RULE_UNIT_MISMATCH",
            f"{name} must use {unit}",
            parameter=name,
            expected_unit=unit,
            supplied_unit=getattr(rule, "unit", None),
        )
    if value < minimum or (maximum is not None and value > maximum):
        raise error(
            422,
            "PLANNING_VALUE_OUT_OF_RANGE",
            f"{name} is outside its supported numeric range",
            parameter=name,
            value=value,
            minimum=minimum,
            maximum=maximum,
        )
    return value


def _orientation_degrees(local_polygon) -> float:
    rectangle = local_polygon.minimum_rotated_rectangle
    coordinates = list(rectangle.exterior.coords)
    edges = list(zip(coordinates, coordinates[1:]))
    if not edges:
        return 0.0
    start, end = max(
        edges,
        key=lambda edge: math.hypot(edge[1][0] - edge[0][0], edge[1][1] - edge[0][1]),
    )
    dx, dy = end[0] - start[0], end[1] - start[1]
    return round(math.degrees(math.atan2(dx, dy)) % 180.0, 3)


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
    if source.geom_type != "Polygon" or not source.is_valid or source.is_empty:
        raise error(422, "INVALID_SITE_GEOMETRY", "A valid, non-empty Polygon site boundary is required")
    forward, inverse = _projected_transformer(boundary)
    local = transform_geometry(forward.transform, source)
    setback = _validated_rule(request.setback_m, name="setback_m", unit="m", minimum=0.0)
    if setback is None:
        setback = 0.0
    buildable = local.buffer(-setback) if setback else local
    if buildable.is_empty or buildable.area <= 0:
        raise error(409, "NO_BUILDABLE_AREA", "Setbacks eliminate the buildable site area")

    max_coverage = _validated_rule(request.max_coverage, name="max_coverage", unit="ratio", minimum=0.0, maximum=1.0)
    far = _validated_rule(request.far, name="far", unit="ratio", minimum=0.0)
    max_height = _validated_rule(request.max_height_m, name="max_height_m", unit="m", minimum=0.0)
    site_area = local.area
    footprint_limit = site_area * max_coverage if max_coverage is not None else None
    far_limit = site_area * far if far is not None else None
    # Coverage limits the building footprint; FAR/FSI limits total gross floor area.
    # They are different quantities and must never be collapsed into one cap.
    max_gfa = far_limit
    violations = []
    unknowns = []
    for name, value in (
        ("max_coverage", max_coverage),
        ("far", far),
        ("max_height_m", max_height),
    ):
        if value is None:
            unknowns.append(name)
    if footprint_limit is not None and footprint_limit > buildable.area:
        violations.append({
            "code": "COVERAGE_EXCEEDS_BUILDABLE_AREA",
            "severity": "INFO",
            "message": "The coverage-derived footprint limit exceeds the setback-derived buildable area; the buildable polygon remains the controlling footprint.",
        })

    orientation = _orientation_degrees(local)
    environmental_unknowns = ["solar_exposure", "prevailing_wind", "climate_context"]
    payload = {
        "schema_version": "s2-envelope-v2",
        "site_area_m2": round(site_area, 3),
        "buildable_area_m2": round(buildable.area, 3),
        "buildable_polygon": mapping(transform_geometry(inverse.transform, buildable)),
        "setback_m": setback,
        "max_coverage": max_coverage,
        "far": far,
        "max_height_m": max_height,
        "max_footprint_m2": None if footprint_limit is None else round(footprint_limit, 3),
        "max_gfa_m2": None if max_gfa is None else round(max_gfa, 3),
        "site_orientation": {
            "long_axis_degrees_from_north": orientation,
            "status": "DERIVED_FROM_SITE_GEOMETRY",
            "method": "longest_axis_of_local_metric_minimum_rotated_rectangle",
        },
        "environmental_context": {
            "solar_exposure": "UNKNOWN",
            "prevailing_wind": "UNKNOWN",
            "climate_context": "UNKNOWN",
            "unknowns": environmental_unknowns,
        },
        "violations": violations,
        "unknowns": sorted(unknowns),
        "planning_evidence": {
            "setback": request.setback_m.model_dump(),
            "max_coverage": request.max_coverage.model_dump() if request.max_coverage else None,
            "far": request.far.model_dump() if request.far else None,
            "max_height_m": request.max_height_m.model_dump() if request.max_height_m else None,
        },
    }
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
        return {"artifact_id": previous.id, "envelope": previous.payload_json, "envelope_hash": payload["envelope_hash"], "idempotent": True}
    artifact = await new_artifact(session, project=project, version=version, world=world, actor=user.id,
        artifact_type="planning_envelope", payload=payload, status="current")
    artifact.output_hash = payload["envelope_hash"]
    await session.commit()
    return {"artifact_id": artifact.id, "envelope": payload, "envelope_hash": payload["envelope_hash"], "idempotent": False}
