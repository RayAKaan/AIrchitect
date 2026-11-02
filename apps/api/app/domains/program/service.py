from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ArtifactVersion, Project, ProjectVersion, RequirementRecord, User, WorldModelRevision
from app.domains.foundation.service import error, resolve_project_version, resolve_world_model
from app.domains.lifecycle.service import canonical_hash, new_artifact

CATALOG = {
    "office": [("Reception", "public", .06), ("Open Work", "primary", .42), ("Meeting", "primary", .10), ("Focus", "secondary", .08), ("Pantry", "service", .04), ("Toilets", "service", .06), ("Circulation", "circulation", .14), ("Core", "service", .10)],
    "retail": [("Sales Floor", "public", .52), ("Entry", "public", .05), ("Stock", "service", .14), ("Staff", "service", .06), ("Toilets", "service", .05), ("Circulation", "circulation", .10), ("Core", "service", .08)],
    "restaurant": [("Dining", "public", .38), ("Entry", "public", .05), ("Kitchen", "service", .22), ("Storage", "service", .08), ("Toilets", "service", .07), ("Circulation", "circulation", .10), ("Core", "service", .10)],
    "residential": [("Living", "public", .25), ("Bedrooms", "private", .30), ("Kitchen", "private", .10), ("Bathrooms", "service", .10), ("Circulation", "circulation", .10), ("Core", "service", .15)],
}

ADJACENCIES = {
    "office": [
        ("Reception", "Open Work", "direct"),
        ("Open Work", "Meeting", "direct"),
        ("Open Work", "Focus", "direct"),
        ("Pantry", "Open Work", "service"),
        ("Toilets", "Core", "service"),
    ],
    "retail": [
        ("Entry", "Sales Floor", "direct"),
        ("Sales Floor", "Stock", "service"),
        ("Staff", "Stock", "service"),
        ("Toilets", "Sales Floor", "visitor_access"),
    ],
    "restaurant": [
        ("Entry", "Dining", "direct"),
        ("Dining", "Kitchen", "service"),
        ("Kitchen", "Storage", "service"),
        ("Toilets", "Dining", "visitor_access"),
    ],
    "residential": [
        ("Living", "Kitchen", "direct"),
        ("Living", "Bedrooms", "direct"),
        ("Bedrooms", "Bathrooms", "direct"),
        ("Kitchen", "Circulation", "direct"),
    ],
}

USE_ALIASES = {
    "commercial_retail": "retail",
    "commercial retail": "retail",
    "retail": "retail",
    "office": "office",
    "restaurant": "restaurant",
    "residential": "residential",
}


def _use(requirements: list[RequirementRecord]) -> str | None:
    for row in reversed(requirements):
        if row.parameter == "building_use" and row.status in {"CONFIRMED", "ASSUMED"}:
            value = str(row.normalized_value_json).strip().lower().replace("-", "_")
            return USE_ALIASES.get(value, value)
    return None


def _world_value(value):
    return value.get("value") if isinstance(value, dict) and "value" in value else value


def build_program(requirements: list[RequirementRecord], world: WorldModelRevision) -> dict:
    confirmed = [r for r in requirements if r.status in {"CONFIRMED", "ASSUMED"}]
    gfa_row = next((r for r in reversed(confirmed) if r.parameter == "target_gfa"), None)
    floors_row = next((r for r in reversed(confirmed) if r.parameter == "floor_count"), None)
    building = world.model_json.get("building") or {}
    site = world.model_json.get("site") or {}
    canonical_gfa = _world_value(building.get("target_gfa"))
    canonical_floors = _world_value(building.get("floor_count"))
    gfa = float(canonical_gfa) if canonical_gfa is not None else (float(gfa_row.normalized_value_json) if gfa_row else None)
    floors = int(canonical_floors) if canonical_floors is not None else (int(floors_row.normalized_value_json) if floors_row else None)
    canonical_use = building.get("use")
    use = str(canonical_use).strip().lower() if isinstance(canonical_use, str) and canonical_use.strip() else _use(requirements)
    if use is not None:
        use = USE_ALIASES.get(use.replace("-", "_"), use.replace("-", "_"))
    if use is None:
        use = "office"
    if use not in CATALOG:
        raise error(409, "UNKNOWN_BUILDING_USE", "Canonical building use is not supported by the program catalog", building_use=use)

    assumptions = []
    unknowns = []
    has_confirmed_use = isinstance(canonical_use, str) and bool(canonical_use.strip()) or _use(requirements) is not None
    if not has_confirmed_use:
        assumptions.append({
            "parameter": "building_use",
            "value": use,
            "unit": None,
            "reason": "Building use was not confirmed. An office template is shown as a provisional starting point and must be reviewed before design decisions.",
        })
    if gfa is None:
        site_area = _world_value(site.get("area"))
        if site_area and floors:
            gfa = float(site_area) * .65 * floors
            assumptions.append({"parameter": "target_gfa", "value": gfa, "unit": "m2", "reason": "Preliminary program target derived from canonical site area, 65% coverage and confirmed floor count."})
        else:
            unknowns.append("target_gfa")
    if floors is None:
        unknowns.append("floor_count")
    if gfa is None:
        raise error(409, "PROGRAM_INPUT_INCOMPLETE", "A target GFA or enough confirmed site/floor information is required to build a bounded program", unknowns=unknowns)
    if not math.isfinite(gfa) or gfa <= 0:
        raise error(409, "PROGRAM_GFA_INVALID", "Target GFA must be a positive finite value", target_gfa_m2=gfa)

    catalog = CATALOG[use]
    raw_targets = (world.model_json.get("properties") or {}).get("program_area_targets", {})
    if not isinstance(raw_targets, dict):
        raise error(409, "PROGRAM_AREA_TARGETS_INVALID", "Canonical program area targets are malformed")
    known_space_types = {name.lower().replace(" ", "_") for name, _, _ in catalog}
    unknown_targets = sorted(set(raw_targets) - known_space_types)
    if unknown_targets:
        raise error(
            409,
            "PROGRAM_SPACE_TYPE_NOT_IN_CURRENT_PROGRAM",
            "One or more explicit space targets do not belong to the current building-use program",
            space_types=unknown_targets,
            building_use=use,
        )
    explicit_targets: dict[str, float] = {}
    for space_type, raw_area in raw_targets.items():
        if isinstance(raw_area, bool) or not isinstance(raw_area, (int, float)) or not math.isfinite(float(raw_area)) or float(raw_area) <= 0:
            raise error(409, "PROGRAM_AREA_TARGETS_INVALID", "Explicit program areas must be positive finite numbers", space_type=space_type)
        rounded_area = round(float(raw_area), 2)
        if rounded_area <= 0:
            raise error(409, "PROGRAM_AREA_TARGETS_INVALID", "Explicit program areas must be at least 0.01 m2", space_type=space_type)
        explicit_targets[space_type] = rounded_area
    explicit_total = sum(explicit_targets.values())
    if explicit_total > gfa + 1e-6:
        raise error(
            409,
            "PROGRAM_AREA_TARGETS_EXCEED_GFA",
            "Explicit space targets exceed the confirmed target GFA",
            explicit_total_m2=round(explicit_total, 2),
            target_gfa_m2=round(gfa, 2),
        )
    remaining_catalog = [
        (name, category, ratio) for name, category, ratio in catalog
        if name.lower().replace(" ", "_") not in explicit_targets
    ]
    remaining_gfa = round(gfa - explicit_total, 2)
    remaining_ratio = sum(ratio for _, _, ratio in remaining_catalog)
    if remaining_catalog and remaining_gfa <= 0:
        raise error(
            409,
            "PROGRAM_AREA_TARGETS_EXHAUST_GFA",
            "Explicit targets leave no area for the remaining required program spaces",
            target_gfa_m2=round(gfa, 2),
        )
    if not remaining_catalog and abs(remaining_gfa) > 0.005:
        raise error(
            409,
            "PROGRAM_AREA_TARGETS_INCOMPLETE",
            "When every program space has an explicit target, their sum must equal target GFA",
            remaining_area_m2=round(remaining_gfa, 2),
        )
    remaining_targets = {
        name.lower().replace(" ", "_"): (
            round(remaining_gfa * ratio / remaining_ratio, 2) if remaining_ratio else 0.0
        )
        for name, _, ratio in remaining_catalog
    }
    if remaining_targets:
        rounding_residual = round(remaining_gfa - sum(remaining_targets.values()), 2)
        adjustment_key = max(remaining_targets, key=remaining_targets.get)
        remaining_targets[adjustment_key] = round(
            remaining_targets[adjustment_key] + rounding_residual, 2
        )

    spaces = []
    for index, (name, category, ratio) in enumerate(catalog, 1):
        space_type = name.lower().replace(" ", "_")
        explicit = space_type in explicit_targets
        target = explicit_targets[space_type] if explicit else remaining_targets.get(space_type, 0.0)
        spaces.append({
            "id": f"space-{index:02d}",
            "name": name,
            "space_type": space_type,
            "category": category,
            "quantity": 1,
            "target_area_m2": target,
            "min_area_m2": round(target * .85, 2),
            "max_area_m2": round(target * 1.15, 2),
            "source": "human_review_program_target" if explicit else "program_template_v1",
            "assumption": False,
        })
    ids = {space["name"]: space["id"] for space in spaces}
    adjacencies = [
        {"from": ids[source], "to": ids[target], "relationship": relationship, "required": True}
        for source, target, relationship in ADJACENCIES[use]
        if source in ids and target in ids
    ]
    total_area = round(sum(space["target_area_m2"] for space in spaces), 2)
    area_residual = round(gfa - total_area, 2)
    if abs(area_residual) > 0.01:
        raise error(
            409,
            "PROGRAM_AREA_RECONCILIATION_FAILED",
            "Generated space targets do not reconcile to the target GFA",
            target_gfa_m2=round(gfa, 2),
            allocated_area_m2=total_area,
            residual_m2=area_residual,
        )
    site_area = _world_value(site.get("area"))
    site_width = _world_value(site.get("width"))
    site_depth = _world_value(site.get("depth"))
    site_context = {
        "site_area_m2": site_area,
        "site_width_m": site_width,
        "site_depth_m": site_depth,
        "boundary_available": bool(site.get("boundary")),
        "orientation_degrees": _world_value(site.get("orientation_degrees")),
        "orientation_status": "KNOWN" if site.get("orientation_degrees") is not None else "UNKNOWN",
        "access_frontage_status": "UNKNOWN",
    }
    if site_context["orientation_status"] == "UNKNOWN":
        unknowns.append("site_orientation")
    unknowns.append("site_access_frontage")
    return {
        "schema_version": "s2-program-v2",
        "use": use,
        "target_gfa_m2": round(gfa, 2),
        "floor_count": floors,
        "spaces": spaces,
        "adjacencies": adjacencies,
        "site_context": site_context,
        "area_reconciliation": {
            "target_gfa_m2": round(gfa, 2),
            "allocated_space_area_m2": total_area,
            "residual_m2": area_residual,
            "reconciled": abs(area_residual) <= 0.01,
        },
        "assumptions": assumptions,
        "unknowns": sorted(set(unknowns)),
        "provenance": {
            "requirement_ids": [r.id for r in confirmed],
            "world_model_hash": world.model_hash,
            "program_area_targets": explicit_targets,
            "engine": "program_template_v2",
        },
    }


async def generate(session: AsyncSession, project_id: str, version_ref: str, user: User) -> dict:
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    world = await resolve_world_model(session, version.id)
    requirements = list((await session.scalars(select(RequirementRecord).where(RequirementRecord.project_version_id == version.id)
        .order_by(RequirementRecord.created_at, RequirementRecord.id))).all())
    if any(r.status == "CONTRADICTORY" for r in requirements):
        raise error(409, "CONTRADICTORY_REQUIREMENTS", "Resolve contradictory requirements before program generation")
    payload = build_program(requirements, world)
    digest = canonical_hash(payload)
    previous = await session.scalar(select(ArtifactVersion).where(ArtifactVersion.project_version_id == version.id,
        ArtifactVersion.artifact_type == "architectural_program").order_by(ArtifactVersion.version.desc()).limit(1))
    if previous and previous.output_hash == digest:
        return {"artifact_id": previous.id, "program": previous.payload_json, "program_hash": digest, "idempotent": True}
    artifact = await new_artifact(session, project=project, version=version, world=world, actor=user.id,
        artifact_type="architectural_program", payload=payload, status="current")
    artifact.output_hash = digest
    await session.commit()
    return {"artifact_id": artifact.id, "program": payload, "program_hash": digest, "idempotent": False}
