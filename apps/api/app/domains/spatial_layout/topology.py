from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from shapely.geometry import Polygon


TOPOLOGY_ENGINE_VERSION = "spatial-topology-v1.0.0"
_GEOMETRY_TOLERANCE_M = 1e-5
_AREA_TOLERANCE_M2 = 0.02
_MAX_LAYOUT_SPACES = 2_000


class SpatialTopologyError(ValueError):
    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None):
        self.code = code
        self.context = context or {}
        super().__init__(message)


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validated_spaces(layout: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Polygon]]:
    rows = layout.get("spaces")
    if not isinstance(rows, list) or not rows:
        raise SpatialTopologyError("TOPOLOGY_SPACES_REQUIRED", "A spatial layout with at least one room is required")
    if len(rows) > _MAX_LAYOUT_SPACES:
        raise SpatialTopologyError(
            "TOPOLOGY_SPACE_LIMIT_EXCEEDED",
            "The layout exceeds the supported topology-analysis space limit",
            {"space_count": len(rows), "maximum": _MAX_LAYOUT_SPACES},
        )

    spaces: dict[str, dict[str, Any]] = {}
    polygons: dict[str, Polygon] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SpatialTopologyError(
                "TOPOLOGY_LAYOUT_INVALID",
                "Every layout space must be an object",
                {"index": index},
            )
        space_id = row.get("id")
        if not isinstance(space_id, str) or not space_id or space_id in spaces:
            raise SpatialTopologyError(
                "TOPOLOGY_SPACE_ID_INVALID",
                "Layout space IDs must be non-empty and unique",
                {"index": index, "space_id": space_id},
            )
        level = row.get("level_number")
        if isinstance(level, bool) or not isinstance(level, int) or level < 1:
            raise SpatialTopologyError(
                "TOPOLOGY_LEVEL_INVALID",
                "Every layout space requires a positive level number",
                {"space_id": space_id},
            )
        boundary = row.get("boundary")
        if not isinstance(boundary, list) or len(boundary) < 4:
            raise SpatialTopologyError(
                "TOPOLOGY_BOUNDARY_INVALID",
                "Every layout space requires a closed polygon boundary",
                {"space_id": space_id},
            )
        coordinates: list[tuple[float, float]] = []
        for point in boundary:
            if (
                not isinstance(point, list)
                or len(point) < 2
                or isinstance(point[0], bool)
                or isinstance(point[1], bool)
                or not isinstance(point[0], (int, float))
                or not isinstance(point[1], (int, float))
                or not math.isfinite(float(point[0]))
                or not math.isfinite(float(point[1]))
            ):
                raise SpatialTopologyError(
                    "TOPOLOGY_BOUNDARY_INVALID",
                    "Space boundary coordinates must be finite metric values",
                    {"space_id": space_id},
                )
            coordinates.append((float(point[0]), float(point[1])))
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        polygon = Polygon(coordinates)
        if polygon.is_empty or not polygon.is_valid or polygon.area <= _AREA_TOLERANCE_M2:
            raise SpatialTopologyError(
                "TOPOLOGY_BOUNDARY_INVALID",
                "Space boundary must form a valid positive-area polygon",
                {"space_id": space_id},
            )
        declared_area = row.get("area_m2")
        if (
            isinstance(declared_area, bool)
            or not isinstance(declared_area, (int, float))
            or not math.isfinite(float(declared_area))
        ):
            raise SpatialTopologyError(
                "TOPOLOGY_AREA_INVALID",
                "Space area must be a finite metric quantity",
                {"space_id": space_id},
            )
        if abs(polygon.area - float(declared_area)) > max(_AREA_TOLERANCE_M2, polygon.area * 1e-4):
            raise SpatialTopologyError(
                "TOPOLOGY_AREA_MISMATCH",
                "Declared space area does not match its polygon geometry",
                {
                    "space_id": space_id,
                    "declared_area_m2": float(declared_area),
                    "polygon_area_m2": round(polygon.area, 6),
                },
            )
        spaces[space_id] = row
        polygons[space_id] = polygon
    return spaces, polygons


def _connected_components(node_ids: list[str], neighbours: dict[str, set[str]]) -> list[list[str]]:
    remaining = set(node_ids)
    components: list[list[str]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component: set[str] = set()
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            stack.extend(sorted(neighbours[node] - component, reverse=True))
        remaining -= component
        components.append(sorted(component))
    return components


def build_spatial_topology(layout: dict[str, Any]) -> dict[str, Any]:
    """Derive a deterministic room adjacency graph from a validated spatial layout.

    Shared boundaries are potential connections, not doors or proof of traversable
    access. Circulation, egress and accessibility remain explicit review gates.
    """
    supplied_hash = layout.get("layout_hash")
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise SpatialTopologyError("TOPOLOGY_LAYOUT_HASH_REQUIRED", "A persisted layout hash is required")
    hash_input = dict(layout)
    hash_input.pop("layout_hash", None)
    if _canonical_hash(hash_input) != supplied_hash:
        raise SpatialTopologyError(
            "TOPOLOGY_LAYOUT_HASH_INVALID",
            "Spatial layout content does not match its persisted hash",
        )

    spaces, polygons = _validated_spaces(layout)
    by_level: dict[int, list[str]] = defaultdict(list)
    for space_id, row in spaces.items():
        by_level[int(row["level_number"])].append(space_id)

    neighbours: dict[str, set[str]] = {space_id: set() for space_id in spaces}
    edges: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for level_number in sorted(by_level):
        ordered_ids = sorted(by_level[level_number], key=lambda item: (polygons[item].bounds[0], item))
        active: list[str] = []
        for space_id in ordered_ids:
            polygon = polygons[space_id]
            min_x, min_y, _, max_y = polygon.bounds
            active = [other for other in active if polygons[other].bounds[2] >= min_x - _GEOMETRY_TOLERANCE_M]
            for other_id in active:
                other = polygons[other_id]
                other_min_y, other_max_y = other.bounds[1], other.bounds[3]
                if other_max_y < min_y - _GEOMETRY_TOLERANCE_M or max_y < other_min_y - _GEOMETRY_TOLERANCE_M:
                    continue
                overlap_area = polygon.intersection(other).area
                if overlap_area > _AREA_TOLERANCE_M2:
                    issues.append({
                        "code": "SPACE_INTERIOR_OVERLAP",
                        "severity": "ERROR",
                        "space_ids": sorted([space_id, other_id]),
                        "overlap_area_m2": round(overlap_area, 6),
                    })
                    continue
                shared_length = polygon.boundary.intersection(other.boundary).length
                if shared_length <= _GEOMETRY_TOLERANCE_M:
                    continue
                first_id, second_id = sorted([space_id, other_id])
                edge_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"airchitect:topology-edge:{layout['project_version_id']}:{first_id}:{second_id}",
                    )
                )
                edges.append({
                    "id": edge_id,
                    "source_space_id": first_id,
                    "target_space_id": second_id,
                    "level_number": level_number,
                    "relationship": "SHARED_BOUNDARY",
                    "shared_boundary_m": round(shared_length, 6),
                    "traversable": False,
                    "opening_status": "REQUIRES_DOOR_OR_OPENING_REVIEW",
                })
                neighbours[first_id].add(second_id)
                neighbours[second_id].add(first_id)
            active.append(space_id)

    components_by_level: list[dict[str, Any]] = []
    for level_number in sorted(by_level):
        node_ids = sorted(by_level[level_number])
        components = _connected_components(node_ids, neighbours)
        components_by_level.append({
            "level_number": level_number,
            "component_count": len(components),
            "components": components,
        })
        if len(components) > 1:
            issues.append({
                "code": "DISCONNECTED_SPATIAL_COMPONENTS",
                "severity": "WARNING",
                "level_number": level_number,
                "component_count": len(components),
                "components": components,
            })

    circulation_ids = {
        space_id for space_id, row in spaces.items()
        if str(row.get("category") or "").casefold() == "circulation"
        or str(row.get("space_type") or "").casefold() == "circulation"
    }
    circulation_edges = [
        edge for edge in edges
        if edge["source_space_id"] in circulation_ids and edge["target_space_id"] in circulation_ids
    ]
    circulation_access: list[dict[str, Any]] = []
    for space_id, row in sorted(spaces.items()):
        if space_id in circulation_ids:
            continue
        adjacent_zones = sorted(neighbours[space_id] & circulation_ids)
        circulation_access.append({
            "space_id": space_id,
            "level_number": row["level_number"],
            "adjacent_circulation_space_ids": adjacent_zones,
            "status": (
                "BOUNDARY_CONTACT_REQUIRES_OPENING_REVIEW"
                if adjacent_zones
                else "NO_DIRECT_CIRCULATION_BOUNDARY"
            ),
            "traversable": False,
        })

    vertical_candidates: list[dict[str, Any]] = []
    by_program_space: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for space_id, row in spaces.items():
        space_type = str(row.get("space_type") or "").casefold()
        category = str(row.get("category") or "").casefold()
        is_vertical_element = (
            space_type in {"core", "vertical_core", "stair", "lift"}
            or category == "vertical_circulation"
        )
        program_space_id = row.get("program_space_id")
        if is_vertical_element and isinstance(program_space_id, str) and program_space_id:
            by_program_space[program_space_id][int(row["level_number"])].append(space_id)
    for program_space_id, levels in sorted(by_program_space.items()):
        ordered_levels = sorted(levels)
        for lower, upper in zip(ordered_levels, ordered_levels[1:]):
            if upper != lower + 1:
                continue
            for lower_id, upper_id in zip(sorted(levels[lower]), sorted(levels[upper])):
                vertical_candidates.append({
                    "source_space_id": lower_id,
                    "target_space_id": upper_id,
                    "program_space_id": program_space_id,
                    "from_level": lower,
                    "to_level": upper,
                    "status": "VERTICAL_CONNECTOR_REQUIRED",
                    "connector_geometry_generated": False,
                })

    program_adjacencies = layout.get("adjacencies") or []
    unresolved_program_adjacencies = [
        item for item in program_adjacencies
        if isinstance(item, dict) and item.get("required") and item.get("status") != "SATISFIED"
    ]
    if unresolved_program_adjacencies:
        issues.append({
            "code": "REQUIRED_PROGRAM_ADJACENCY_UNRESOLVED",
            "severity": "WARNING",
            "count": len(unresolved_program_adjacencies),
        })
    spaces_without_circulation_boundary = [
        item["space_id"] for item in circulation_access
        if item["status"] == "NO_DIRECT_CIRCULATION_BOUNDARY"
    ]
    if spaces_without_circulation_boundary:
        issues.append({
            "code": "SPACES_WITHOUT_CIRCULATION_BOUNDARY",
            "severity": "WARNING",
            "space_ids": spaces_without_circulation_boundary,
        })

    unknowns = [
        "door_and_opening_locations",
        "traversable_access_routes",
        "accessible_routes",
        "fire_egress_and_exit_distances",
        "vertical_circulation_geometry",
        "fire_and_smoke_compartmentation",
    ]
    if not circulation_ids:
        unknowns.append("circulation_zones")
    if not layout.get("source_lineage", {}).get("envelope_source_lineage", {}).get("site_revision_id"):
        unknowns.append("site_revision_lineage")

    payload = {
        "schema_version": "phase3-spatial-topology-v1",
        "engine_version": TOPOLOGY_ENGINE_VERSION,
        "status": "REVIEW_REQUIRED" if unknowns or issues else "PRELIMINARY",
        "project_id": layout.get("project_id"),
        "project_version_id": layout.get("project_version_id"),
        "world_model_hash": layout.get("world_model_hash"),
        "layout_hash": supplied_hash,
        "selected_alternative_id": layout.get("selected_alternative_id"),
        "nodes": [
            {
                "id": space_id,
                "program_space_id": row.get("program_space_id"),
                "space_type": row.get("space_type"),
                "category": row.get("category"),
                "level_number": row.get("level_number"),
                "area_m2": row.get("area_m2"),
                "neighbour_ids": sorted(neighbours[space_id]),
                "circulation_zone": space_id in circulation_ids,
            }
            for space_id, row in sorted(spaces.items())
        ],
        "edges": sorted(
            edges,
            key=lambda item: (item["level_number"], item["source_space_id"], item["target_space_id"]),
        ),
        "boundary_adjacency_components": components_by_level,
        "circulation_network": {
            "status": "CANDIDATE_ONLY" if circulation_ids else "UNKNOWN",
            "node_ids": sorted(circulation_ids),
            "edges": circulation_edges,
            "space_boundary_contacts": circulation_access,
            "traversable": False,
        },
        "vertical_connectivity_candidates": vertical_candidates,
        "program_adjacencies": program_adjacencies,
        "issues": issues,
        "unknowns": sorted(set(unknowns)),
        "assumptions": [
            "A shared polygon boundary is a potential connection, not evidence of a door or traversable opening.",
            "Circulation zones are identified only from explicit programme categories; "
            "no corridor geometry is invented.",
            "Vertical correspondence is a candidate relationship only; stairs, ramps and lifts are not inferred.",
        ],
        "source_lineage": {
            "world_model_hash": layout.get("world_model_hash"),
            "layout_hash": supplied_hash,
            "selected_alternative_id": layout.get("selected_alternative_id"),
            "program_hash": layout.get("program_hash"),
            "envelope_hash": layout.get("envelope_hash"),
            "envelope_source_lineage": layout.get("source_lineage", {}).get("envelope_source_lineage", {}),
        },
    }
    payload["topology_hash"] = _canonical_hash(payload)
    return payload


__all__ = ["TOPOLOGY_ENGINE_VERSION", "SpatialTopologyError", "build_spatial_topology"]
