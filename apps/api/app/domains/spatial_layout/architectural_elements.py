from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from shapely.geometry import Polygon
from shapely.ops import unary_union


ENGINE_VERSION = "architectural-elements-v1.0.0"
_AREA_TOLERANCE_M2 = 0.02
_GEOMETRY_TOLERANCE_M = 1e-6
_MAX_SPACES = 2_000
Point3 = tuple[float, float, float]


class ArchitecturalElementError(ValueError):
    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None):
        self.code = code
        self.context = context or {}
        super().__init__(message)


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _verified_payload(payload: dict[str, Any], hash_key: str, code: str) -> str:
    supplied = payload.get(hash_key)
    if not isinstance(supplied, str) or len(supplied) != 64:
        raise ArchitecturalElementError(f"{code}_HASH_REQUIRED", f"A persisted {hash_key} is required")
    source = dict(payload)
    source.pop(hash_key, None)
    if _hash(source) != supplied:
        raise ArchitecturalElementError(f"{code}_HASH_INVALID", f"{hash_key} does not match the artifact content")
    return supplied


def _coordinate(point: Any, *, space_id: str) -> tuple[float, float, float]:
    if not isinstance(point, list) or len(point) != 3:
        raise ArchitecturalElementError(
            "ELEMENT_BOUNDARY_INVALID",
            "Every room boundary coordinate must contain x, y and z in metres",
            {"space_id": space_id},
        )
    values: list[float] = []
    for value in point:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ArchitecturalElementError(
                "ELEMENT_BOUNDARY_INVALID",
                "Room boundary coordinates must be finite metric values",
                {"space_id": space_id},
            )
        values.append(float(value))
    return values[0], values[1], values[2]


def _interpolate_point(first: Point3, second: Point3, t_first: float, t_second: float, t: float) -> Point3:
    ratio = (t - t_first) / (t_second - t_first)
    return (
        round(first[0] + ratio * (second[0] - first[0]), 6),
        round(first[1] + ratio * (second[1] - first[1]), 6),
        round(first[2] + ratio * (second[2] - first[2]), 6),
    )


def compile_architectural_elements(
    layout: dict[str, Any],
    topology: dict[str, Any],
    *,
    default_wall_thickness_m: float | None = None,
) -> dict[str, Any]:
    """Create deterministic, reviewable architectural element proposals.

    This compiler only derives wall axes from validated room polygon boundaries.
    It does not invent wall heights, thicknesses, openings, slabs, stairs or roofs.
    The output is a proposal artifact, not a canonical World Model mutation.
    """
    layout_hash = _verified_payload(layout, "layout_hash", "ELEMENT_LAYOUT")
    topology_hash = _verified_payload(topology, "topology_hash", "ELEMENT_TOPOLOGY")
    topology_lineage = topology.get("source_lineage") or {}
    if topology_lineage.get("layout_hash") != layout_hash:
        raise ArchitecturalElementError(
            "ELEMENT_TOPOLOGY_STALE",
            "Spatial topology was not derived from this exact spatial layout",
        )
    if topology.get("world_model_hash") != layout.get("world_model_hash"):
        raise ArchitecturalElementError(
            "ELEMENT_WORLD_MODEL_MISMATCH",
            "Spatial topology and layout use different World Model revisions",
        )
    if default_wall_thickness_m is not None and (
        isinstance(default_wall_thickness_m, bool)
        or not isinstance(default_wall_thickness_m, (int, float))
        or not math.isfinite(float(default_wall_thickness_m))
        or not 0.05 <= float(default_wall_thickness_m) <= 1.0
    ):
        raise ArchitecturalElementError(
            "ELEMENT_WALL_THICKNESS_INVALID",
            "A supplied wall thickness design parameter must be between 0.05 m and 1.0 m",
        )

    rows = layout.get("spaces")
    if not isinstance(rows, list) or not rows or len(rows) > _MAX_SPACES:
        raise ArchitecturalElementError(
            "ELEMENT_SPACES_INVALID",
            "A non-empty layout with at most 2,000 spaces is required",
        )

    spaces: dict[str, dict[str, Any]] = {}
    polygons: dict[str, Polygon] = {}
    raw_segments_by_level: dict[int, list[tuple[Point3, Point3, str]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            raise ArchitecturalElementError("ELEMENT_SPACE_INVALID", "Every layout space must be an object")
        space_id = row.get("id")
        level = row.get("level_number")
        if not isinstance(space_id, str) or not space_id or space_id in spaces:
            raise ArchitecturalElementError(
                "ELEMENT_SPACE_ID_INVALID",
                "Layout space IDs must be non-empty and unique",
                {"space_id": space_id},
            )
        if isinstance(level, bool) or not isinstance(level, int) or level < 1:
            raise ArchitecturalElementError(
                "ELEMENT_LEVEL_INVALID",
                "Every layout space requires a positive level number",
                {"space_id": space_id},
            )
        boundary = row.get("boundary")
        if not isinstance(boundary, list) or len(boundary) < 4:
            raise ArchitecturalElementError(
                "ELEMENT_BOUNDARY_INVALID",
                "Every room requires a closed polygon boundary",
                {"space_id": space_id},
            )
        points = [_coordinate(point, space_id=space_id) for point in boundary]
        if points[0] != points[-1]:
            points.append(points[0])
        elevations = [point[2] for point in points]
        if max(elevations) - min(elevations) > _GEOMETRY_TOLERANCE_M:
            raise ArchitecturalElementError(
                "ELEMENT_BOUNDARY_NON_PLANAR",
                "A room boundary must lie on one horizontal storey elevation",
                {"space_id": space_id, "minimum_elevation_m": min(elevations),
                 "maximum_elevation_m": max(elevations)},
            )
        polygon = Polygon([(point[0], point[1]) for point in points])
        declared_area = row.get("area_m2")
        if (
            not polygon.is_valid
            or polygon.is_empty
            or isinstance(declared_area, bool)
            or not isinstance(declared_area, (int, float))
            or not math.isfinite(float(declared_area))
            or abs(polygon.area - float(declared_area)) > max(_AREA_TOLERANCE_M2, polygon.area * 1e-4)
        ):
            raise ArchitecturalElementError(
                "ELEMENT_SPACE_GEOMETRY_INVALID",
                "Room polygon must be valid and reconcile to its declared area",
                {"space_id": space_id},
            )
        spaces[space_id] = row
        polygons[space_id] = polygon
        for first, second in zip(points, points[1:]):
            if math.dist(first, second) <= _GEOMETRY_TOLERANCE_M:
                continue
            raw_segments_by_level[level].append((first, second, space_id))

    # Node collinear boundaries before emitting elements. Exact endpoint matching
    # misses T-junctions and differently segmented shared boundaries, producing
    # overlapping duplicate walls. Canonical line groups make this deterministic
    # while keeping the work local to each collinear group.
    segments_by_level: dict[int, dict[tuple[Point3, Point3], set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for level, raw_segments in sorted(raw_segments_by_level.items()):
        line_groups: dict[
            tuple[float, float, float],
            list[tuple[float, float, Point3, Point3, str]],
        ] = defaultdict(list)
        for first, second, owner_id in raw_segments:
            dx = second[0] - first[0]
            dy = second[1] - first[1]
            length_xy = math.hypot(dx, dy)
            if length_xy <= _GEOMETRY_TOLERANCE_M:
                continue
            ux, uy = dx / length_xy, dy / length_xy
            if ux < -_GEOMETRY_TOLERANCE_M or (
                abs(ux) <= _GEOMETRY_TOLERANCE_M and uy < 0
            ):
                ux, uy = -ux, -uy
            offset = ux * first[1] - uy * first[0]
            line_key = (round(ux, 6), round(uy, 6), round(offset, 6))
            start_t = first[0] * ux + first[1] * uy
            end_t = second[0] * ux + second[1] * uy
            line_groups[line_key].append((min(start_t, end_t), max(start_t, end_t), first, second, owner_id))

        for line_key, group in line_groups.items():
            ux, uy = line_key[0], line_key[1]
            breakpoints = sorted({
                round(value, 6)
                for start_t, end_t, *_ in group
                for value in (start_t, end_t)
            })
            for start_t, end_t, first, second, owner_id in group:
                t_first = first[0] * ux + first[1] * uy
                t_second = second[0] * ux + second[1] * uy
                low, high = sorted((t_first, t_second))
                cuts = [
                    value for value in breakpoints
                    if low - _GEOMETRY_TOLERANCE_M <= value <= high + _GEOMETRY_TOLERANCE_M
                ]
                for cut_start, cut_end in zip(cuts, cuts[1:]):
                    if cut_end - cut_start <= _GEOMETRY_TOLERANCE_M:
                        continue
                    a = _interpolate_point(first, second, t_first, t_second, cut_start)
                    b = _interpolate_point(first, second, t_first, t_second, cut_end)
                    ordered = tuple(sorted((a, b)))
                    segments_by_level[level][ordered].add(owner_id)

    topology_nodes = topology.get("nodes")
    if not isinstance(topology_nodes, list):
        raise ArchitecturalElementError("ELEMENT_TOPOLOGY_NODES_REQUIRED", "Topology nodes are required")
    topology_space_ids = {
        node.get("id") for node in topology_nodes
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    if topology_space_ids != set(spaces):
        raise ArchitecturalElementError(
            "ELEMENT_TOPOLOGY_NODES_MISMATCH",
            "Topology nodes must match the exact source layout space set",
            {
                "missing_node_ids": sorted(set(spaces) - topology_space_ids),
                "unknown_node_ids": sorted(topology_space_ids - set(spaces)),
            },
        )
    topology_edges_by_pair = {
        tuple(sorted((edge.get("source_space_id"), edge.get("target_space_id")))): edge.get("id")
        for edge in topology.get("edges", [])
        if isinstance(edge, dict)
        and edge.get("relationship") == "SHARED_BOUNDARY"
        and isinstance(edge.get("id"), str)
    }

    candidates: list[dict[str, Any]] = []
    for level, segments in sorted(segments_by_level.items()):
        for (start, end), owners in sorted(segments.items()):
            length = math.dist(start[:2], end[:2])
            if length <= _GEOMETRY_TOLERANCE_M:
                continue
            owner_ids = sorted(owners)
            if len(owner_ids) > 2:
                raise ArchitecturalElementError(
                    "ELEMENT_BOUNDARY_NON_MANIFOLD",
                    "A wall segment cannot be shared by more than two spaces",
                    {"level_number": level, "space_ids": owner_ids},
                )
            topology_edge_ids: list[str] = []
            if len(owner_ids) == 2:
                edge_id = topology_edges_by_pair.get(tuple(owner_ids))
                if edge_id is None:
                    raise ArchitecturalElementError(
                        "ELEMENT_TOPOLOGY_BOUNDARY_MISMATCH",
                        "A shared wall segment has no matching topology edge",
                        {"level_number": level, "space_ids": owner_ids},
                    )
                topology_edge_ids.append(edge_id)
            element_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"airchitect:architectural-wall:{layout['project_version_id']}:{level}:{start}:{end}",
                )
            )
            properties: dict[str, Any] = {
                "level_number": level,
                "start_m": {"x": start[0], "y": start[1], "z": start[2]},
                "end_m": {"x": end[0], "y": end[1], "z": end[2]},
                "length_m": round(length, 6),
            }
            missing = ["height_m", "thickness_m"]
            if default_wall_thickness_m is not None:
                properties["thickness_m"] = float(default_wall_thickness_m)
                missing.remove("thickness_m")
            candidates.append({
                "candidate_id": element_id,
                "element_type": "Wall",
                "name": f"{'Partition' if len(owner_ids) > 1 else 'Perimeter'} wall — Level {level}",
                "properties": properties,
                "relationship_candidates": [
                    {"relationship_type": "hosts_element", "target_id": space_id}
                    for space_id in owner_ids
                ],
                "source_space_ids": owner_ids,
                "topology_edge_ids": topology_edge_ids,
                "level_number": level,
                "wall_classification": "PARTITION" if len(owner_ids) > 1 else "PERIMETER",
                "status": "UNDERCONSTRAINED" if missing else "REVIEW_REQUIRED",
                "missing_parameters": missing,
                "assumptions": (
                    ["Wall thickness is an explicitly supplied design parameter, not a code minimum."]
                    if default_wall_thickness_m is not None else []
                ),
                "geometry": {
                    "coordinate_system": "local_cartesian_z_up",
                    "units": "m",
                    "axis_start_m": list(start),
                    "axis_end_m": list(end),
                },
            })

    slab_candidates: list[dict[str, Any]] = []
    slab_unknowns: set[str] = set()
    for level in sorted(raw_segments_by_level):
        level_rows = [row for row in rows if row.get("level_number") == level]
        level_elevations = {
            round(float(point[2]), 6)
            for row in level_rows
            for point in row.get("boundary", [])
            if isinstance(point, list) and len(point) == 3
        }
        if len(level_elevations) != 1:
            slab_unknowns.add(f"slab_level_{level}_elevation_mismatch")
            continue
        elevation = next(iter(level_elevations))
        union = unary_union([polygons[row["id"]] for row in level_rows])
        components = list(union.geoms) if union.geom_type == "MultiPolygon" else [union]
        for component_index, component in enumerate(sorted(
            components,
            key=lambda item: (round(item.bounds[1], 6), round(item.bounds[0], 6), round(item.area, 6)),
        )):
            if component.geom_type != "Polygon" or not component.is_valid or component.is_empty:
                slab_unknowns.add(f"slab_level_{level}_invalid_union")
                continue
            if component.interiors:
                slab_unknowns.add(f"slab_level_{level}_void_boundary_requires_explicit_opening_geometry")
                continue
            ring_xy = [(round(float(x), 6), round(float(y), 6)) for x, y in component.exterior.coords]
            if len(ring_xy) < 4 or ring_xy[0] != ring_xy[-1]:
                slab_unknowns.add(f"slab_level_{level}_boundary_invalid")
                continue
            boundary = [
                {"x": x, "y": y, "z": elevation}
                for x, y in ring_xy
            ]
            boundary_key = json.dumps(boundary, sort_keys=True, separators=(",", ":"))
            element_id = str(uuid5(
                NAMESPACE_URL,
                f"airchitect:architectural-slab:{layout['project_version_id']}:{level}:{boundary_key}",
            ))
            source_space_ids = sorted(row["id"] for row in level_rows
                                      if polygons[row["id"]].intersection(component).area > _AREA_TOLERANCE_M2)
            storey_id = str(uuid5(NAMESPACE_URL, f"airchitect:{layout['project_id']}:Storey:level:{level}"))
            slab_candidates.append({
                "candidate_id": element_id,
                "element_type": "Slab",
                "name": f"Floor slab — Level {level}",
                "properties": {
                    "level_number": level,
                    "boundary_m": boundary,
                    "area_m2": round(float(component.area), 6),
                },
                "relationship_candidates": [{
                    "relationship_type": "hosts_element",
                    "source_id": storey_id,
                    "target_id": element_id,
                }],
                "source_space_ids": source_space_ids,
                "level_number": level,
                "status": "UNDERCONSTRAINED",
                "missing_parameters": ["thickness_m"],
                "assumptions": [],
                "geometry": {
                    "coordinate_system": "local_cartesian_z_up",
                    "units": "m",
                    "boundary_m": boundary,
                    "area_m2": round(float(component.area), 6),
                    "component_index": component_index,
                },
            })

    candidates.extend(slab_candidates)
    unresolved = sorted(set(topology.get("unknowns") or []))
    payload = {
        "schema_version": "phase3-architectural-elements-v1",
        "engine_version": ENGINE_VERSION,
        "project_id": layout.get("project_id"),
        "project_version_id": layout.get("project_version_id"),
        "world_model_hash": layout.get("world_model_hash"),
        "layout_hash": layout_hash,
        "topology_hash": topology_hash,
        "selected_alternative_id": layout.get("selected_alternative_id"),
        "status": "REVIEW_REQUIRED" if candidates else "UNDERCONSTRAINED",
        "candidates": candidates,
        "counts": {
            "wall_candidates": sum(item["element_type"] == "Wall" for item in candidates),
            "slab_candidates": len(slab_candidates),
            "perimeter_walls": sum(item.get("wall_classification") == "PERIMETER" for item in candidates),
            "partition_walls": sum(item.get("wall_classification") == "PARTITION" for item in candidates),
        },
        "not_generated": [
            "roof",
            "doors",
            "windows",
            "stairs",
            "ramps",
        ],
        "unknowns": sorted(set(unresolved + [
            "wall_heights_and_levels",
            "wall_thicknesses_unless_explicitly_supplied",
            "door_and_window_locations",
            "slab_edge_and_opening_geometry",
            "stair_and_ramp_geometry",
            "slab_thickness_m",
            *sorted(slab_unknowns),
            "fire_and_accessibility_requirements",
        ])),
        "source_lineage": {
            "world_model_hash": layout.get("world_model_hash"),
            "layout_hash": layout_hash,
            "topology_hash": topology_hash,
            "alternative_id": layout.get("selected_alternative_id"),
        },
    }
    payload["elements_hash"] = _hash(payload)
    return payload


__all__ = ["ENGINE_VERSION", "ArchitecturalElementError", "compile_architectural_elements"]
