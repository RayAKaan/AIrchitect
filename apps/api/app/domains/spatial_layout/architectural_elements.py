from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from shapely.geometry import Polygon


ENGINE_VERSION = "architectural-elements-v1.0.0"
_AREA_TOLERANCE_M2 = 0.02
_GEOMETRY_TOLERANCE_M = 1e-6
_MAX_SPACES = 2_000


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
    segments_by_level: dict[int, dict[tuple[tuple[float, float, float], tuple[float, float, float]], set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
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
            ordered = tuple(sorted((tuple(round(value, 6) for value in first),
                                   tuple(round(value, 6) for value in second))))
            segments_by_level[level][ordered].add(space_id)

    candidates: list[dict[str, Any]] = []
    for level, segments in sorted(segments_by_level.items()):
        for (start, end), owners in sorted(segments.items()):
            length = math.dist(start[:2], end[:2])
            if length <= _GEOMETRY_TOLERANCE_M:
                continue
            owner_ids = sorted(owners)
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
            "wall_candidates": len(candidates),
            "perimeter_walls": sum(item["wall_classification"] == "PERIMETER" for item in candidates),
            "partition_walls": sum(item["wall_classification"] == "PARTITION" for item in candidates),
        },
        "not_generated": [
            "slabs",
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
