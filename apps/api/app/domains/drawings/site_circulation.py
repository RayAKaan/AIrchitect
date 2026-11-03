from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from shapely.geometry import Polygon, box

from app.domains.model import ArchitecturalModel, model_hash


ENGINE_VERSION = "site-circulation-v1.0.0"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _ring(polygon: Polygon) -> list[list[float]]:
    return [[round(float(x), 6), round(float(y), 6)] for x, y in polygon.exterior.coords]


def build_site_circulation_package(model: ArchitecturalModel) -> dict[str, Any]:
    """Derive a site plan and evidence-limited circulation graph from canonical geometry.

    The site boundary is the canonical rectangular Site extent. Hosted doors and
    declared wall-space relationships are represented as access candidates only:
    a host relationship is not proof of a traversable route, exterior entrance,
    accessibility, fire egress, or connection to a public way.
    """
    site = model.site
    site_polygon = box(
        site.origin.x,
        site.origin.y,
        site.origin.x + site.width_m,
        site.origin.y + site.depth_m,
    )
    if not site_polygon.is_valid or site_polygon.area <= 0:
        raise ValueError("SITE_PLAN_BOUNDARY_INVALID")

    footprint_sources: dict[str, list[Polygon]] = {}
    for slab in model.slabs:
        polygon = Polygon([(p.x, p.y) for p in slab.boundary])
        if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
            raise ValueError(f"SITE_PLAN_SLAB_INVALID:{slab.id}")
        footprint_sources.setdefault(slab.level_id or "unassigned", []).append(polygon)
    if not footprint_sources:
        for space in model.spaces:
            polygon = Polygon([(p.x, p.y) for p in space.boundary])
            if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
                raise ValueError(f"SITE_PLAN_SPACE_INVALID:{space.id}")
            footprint_sources.setdefault(space.level_id, []).append(polygon)

    footprints: list[dict[str, Any]] = []
    for level_id, polygons in sorted(footprint_sources.items()):
        for index, polygon in enumerate(sorted(polygons, key=lambda item: (item.bounds, item.area))):
            outside = polygon.difference(site_polygon).area
            footprints.append({
                "id": f"footprint:{level_id}:{index + 1}",
                "level_id": None if level_id == "unassigned" else level_id,
                "boundary": _ring(polygon),
                "area_m2": round(polygon.area, 6),
                "within_site": outside <= 1e-6,
                "outside_site_area_m2": round(outside, 6),
                "source_element_ids": sorted(
                    slab.id for slab in model.slabs
                    if (slab.level_id or "unassigned") == level_id
                    and Polygon([(p.x, p.y) for p in slab.boundary]).equals(polygon)
                ) or sorted(
                    space.id for space in model.spaces
                    if space.level_id == level_id
                    and Polygon([(p.x, p.y) for p in space.boundary]).equals(polygon)
                ),
            })

    wall_by_id = {wall.id: wall for wall in model.walls}
    access_candidates: list[dict[str, Any]] = []
    for door in sorted(model.doors, key=lambda item: item.id):
        wall = wall_by_id[door.host_wall_id]
        length = math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)
        if length <= 1e-9:
            raise ValueError(f"SITE_PLAN_ZERO_LENGTH_HOST_WALL:{wall.id}")
        if door.offset_m + door.width_m > length + 1e-9:
            raise ValueError(f"SITE_PLAN_DOOR_OUTSIDE_HOST:{door.id}")
        ratio = (door.offset_m + door.width_m / 2) / length
        point = [
            round(wall.start.x + (wall.end.x - wall.start.x) * ratio, 6),
            round(wall.start.y + (wall.end.y - wall.start.y) * ratio, 6),
            round(wall.start.z, 6),
        ]
        access_candidates.append({
            "id": door.id,
            "level_id": door.level_id,
            "point": point,
            "host_wall_id": wall.id,
            "adjacent_space_ids": sorted(wall.space_ids),
            "classification": "HOSTED_DOOR_CANDIDATE",
            "route_status": "UNVERIFIED",
            "limitations": [
                "door_operability_not_verified",
                "exterior_or_interior_wall_status_not_verified",
                "connection_to_site_boundary_or_public_way_not_verified",
                "accessibility_and_egress_not_assessed",
            ],
        })

    circulation_nodes = [
        {"id": space.id, "level_id": space.level_id, "node_type": "SPACE"}
        for space in sorted(model.spaces, key=lambda item: item.id)
    ]
    circulation_edges = []
    for door in sorted(model.doors, key=lambda item: item.id):
        wall = wall_by_id[door.host_wall_id]
        if len(wall.space_ids) == 2:
            circulation_edges.append({
                "id": door.id,
                "source_space_id": sorted(wall.space_ids)[0],
                "target_space_id": sorted(wall.space_ids)[1],
                "opening_id": door.id,
                "relationship": "DOOR_HOSTED_ON_SHARED_WALL",
                "traversable": False,
                "verification_status": "REQUIRES_GEOMETRY_AND_CODE_REVIEW",
            })
        elif len(wall.space_ids) > 2:
            raise ValueError(f"SITE_PLAN_HOST_WALL_SPACE_CARDINALITY_INVALID:{wall.id}")

    payload = {
        "schema_version": "site-circulation-package-v1",
        "engine_version": ENGINE_VERSION,
        "source_model_hash": model_hash(model),
        "units": "m",
        "coordinate_system": "local_cartesian_z_up",
        "site": {
            "id": site.id,
            "boundary": _ring(site_polygon),
            "area_m2": round(site_polygon.area, 6),
            "dimensions_m": {"width": site.width_m, "depth": site.depth_m},
            "origin": [site.origin.x, site.origin.y, site.origin.z],
        },
        "building_footprints": footprints,
        "access_candidates": access_candidates,
        "circulation": {
            "nodes": circulation_nodes,
            "edges": circulation_edges,
            "route_geometry": [],
            "status": "CANDIDATE_GRAPH_ONLY",
            "unknowns": [
                "no_explicit_site_access_or_public_way_geometry",
                "no_verified_door_clear_width_or_swing",
                "no_accessibility_route_or_slope_data",
                "no_fire_egress_or_travel_distance_analysis",
                "no_vertical_circulation_route_geometry",
            ],
        },
        "site_constraints": {
            "footprints_within_site": all(item["within_site"] for item in footprints),
            "outside_site_area_m2": round(sum(item["outside_site_area_m2"] for item in footprints), 6),
        },
    }
    payload["package_hash"] = _digest(payload)
    return payload


__all__ = ["ENGINE_VERSION", "build_site_circulation_package"]
