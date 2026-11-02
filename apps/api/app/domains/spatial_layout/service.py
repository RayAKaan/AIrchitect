from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pyproj import CRS, Transformer
from shapely.affinity import rotate, translate
from shapely.geometry import MultiPolygon, Polygon, box, shape
from shapely.ops import transform as transform_geometry


ENGINE_VERSION = "spatial-layout-v1.0.0"
_COORDINATE_SYSTEM = "local_cartesian_z_up"
_TOLERANCE_M = 1e-6


class SpatialLayoutError(ValueError):
    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None):
        self.code = code
        self.context = context or {}
        super().__init__(message)


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finite(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise SpatialLayoutError("LAYOUT_INPUT_INVALID", f"{field} must be a finite number", {"field": field})
    result = float(value)
    if positive and result <= 0:
        raise SpatialLayoutError(
            "LAYOUT_INPUT_INVALID",
            f"{field} must be positive",
            {"field": field, "value": result},
        )
    return result


def _local_polygon(buildable_geojson: dict[str, Any]) -> tuple[Polygon, Transformer]:
    try:
        geographic = shape(buildable_geojson)
    except (TypeError, ValueError) as exc:
        raise SpatialLayoutError("LAYOUT_ENVELOPE_INVALID", "The buildable envelope is not valid GeoJSON") from exc
    if isinstance(geographic, MultiPolygon):
        if len(geographic.geoms) != 1:
            raise SpatialLayoutError(
                "LAYOUT_DISCONNECTED_ENVELOPE",
                "The buildable envelope contains disconnected components; "
                "select a connected building footprint before layout generation",
                {"component_count": len(geographic.geoms)},
            )
        geographic = geographic.geoms[0]
    if not isinstance(geographic, Polygon) or geographic.is_empty or not geographic.is_valid:
        raise SpatialLayoutError("LAYOUT_ENVELOPE_INVALID", "A valid Polygon buildable envelope is required")
    centroid = geographic.centroid
    local_crs = CRS.from_proj4(
        f"+proj=aeqd +lat_0={centroid.y:.10f} +lon_0={centroid.x:.10f} +datum=WGS84 +units=m +no_defs"
    )
    transformer = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True)
    local = transform_geometry(transformer.transform, geographic)
    if not isinstance(local, Polygon) or local.is_empty or not local.is_valid or local.area <= 0:
        raise SpatialLayoutError("LAYOUT_ENVELOPE_INVALID", "The projected buildable envelope is not a usable polygon")
    return local, transformer


def _candidate_centres(polygon: Polygon, translation_x: float, translation_y: float) -> list[tuple[float, float]]:
    target = polygon.centroid
    target_x, target_y = target.x + translation_x, target.y + translation_y
    preferred = (target_x, target_y)
    if abs(translation_x) > _TOLERANCE_M or abs(translation_y) > _TOLERANCE_M:
        # A canonical MoveBuilding command is an exact placement delta. Never
        # silently relocate a user-moved building to a different feasible point.
        return [preferred]

    points: list[tuple[float, float]] = [preferred]
    representative = polygon.representative_point()
    points.append((representative.x, representative.y))

    min_x, min_y, max_x, max_y = polygon.bounds
    eroded = polygon.buffer(-0.5)
    if not eroded.is_empty:
        safe_point = eroded.representative_point()
        points.append((safe_point.x, safe_point.y))

    # A bounded deterministic grid handles concave sites whose centroid and
    # representative point are not suitable centres for the selected footprint.
    for x_index in range(15):
        x = min_x + (max_x - min_x) * x_index / 14
        for y_index in range(15):
            y = min_y + (max_y - min_y) * y_index / 14
            point = (x, y)
            if polygon.covers(shape({"type": "Point", "coordinates": point})):
                points.append(point)

    unique = set(points)
    return sorted(unique, key=lambda point: (
        (point[0] - target_x) ** 2 + (point[1] - target_y) ** 2,
        point[0],
        point[1],
    ))


def _fit_footprint(
    polygon: Polygon,
    width: float,
    depth: float,
    orientation_degrees: float,
    translation_x: float,
    translation_y: float,
) -> tuple[Polygon, tuple[float, float]]:
    base = box(-width / 2, -depth / 2, width / 2, depth / 2)
    centres = _candidate_centres(polygon, translation_x, translation_y)
    for angle in (orientation_degrees,):
        rotated = rotate(base, angle, origin=(0, 0), use_radians=False)
        for centre_x, centre_y in centres:
            candidate = translate(rotated, xoff=centre_x, yoff=centre_y)
            if polygon.buffer(_TOLERANCE_M).covers(candidate):
                return candidate, (centre_x, centre_y)
    raise SpatialLayoutError(
        "LAYOUT_FOOTPRINT_NOT_CONTAINED",
        "The selected concept footprint cannot be placed wholly inside the current buildable envelope",
        {"footprint_width_m": width, "footprint_depth_m": depth, "buildable_area_m2": round(polygon.area, 3)},
    )


def _space_order(spaces: list[dict[str, Any]], adjacencies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    neighbours: dict[str, set[str]] = defaultdict(set)
    for edge in adjacencies:
        first, second = str(edge["from"]), str(edge["to"])
        neighbours[first].add(second)
        neighbours[second].add(first)

    remaining = {str(space["instance_id"]): space for space in spaces}
    ordered: list[dict[str, Any]] = []
    current_program_id: str | None = None
    while remaining:
        available = list(remaining.values())
        adjacent = [space for space in available if current_program_id is not None
                    and space["id"] in neighbours[current_program_id]]
        candidates = adjacent or available
        selected = min(candidates, key=lambda space: (
            -len(neighbours[str(space["id"])]),
            str(space["id"]),
            int(space["instance_number"]),
            str(space["instance_id"]),
        ))
        ordered.append(selected)
        remaining.pop(str(selected["instance_id"]))
        current_program_id = str(selected["id"])
    return ordered


def _point3(x: float, y: float, z: float) -> list[float]:
    return [round(x, 6), round(y, 6), round(z, 6)]


def _transform_ring(
    bounds: tuple[tuple[float, float], ...],
    *,
    centre: tuple[float, float],
    rotation_degrees: float,
    elevation_m: float,
) -> list[list[float]]:
    angle = math.radians(rotation_degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    cx, cy = centre
    return [
        _point3(cx + x * cosine - y * sine, cy + x * sine + y * cosine, elevation_m)
        for x, y in bounds
    ]


def build_spatial_layout(
    *,
    project_id: str,
    project_version_id: str,
    world_model_hash: str,
    program: dict[str, Any],
    envelope: dict[str, Any],
    alternative_id: str,
    design_parameters: dict[str, Any],
    design_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Compile a reviewed programme and selected massing into deterministic floor layouts.

    The result is a derived, editable 2D layout artifact. It does not mutate the
    canonical World Model and does not claim circulation, egress, door placement,
    or code compliance; those are explicit downstream review/implementation gates.
    """
    spaces = program.get("spaces")
    if not isinstance(spaces, list) or not spaces:
        raise SpatialLayoutError("LAYOUT_PROGRAM_INVALID", "The current programme has no spaces")
    floors_raw = program.get("floor_count")
    if isinstance(floors_raw, bool) or not isinstance(floors_raw, int) or floors_raw < 1:
        raise SpatialLayoutError(
            "LAYOUT_FLOOR_COUNT_UNKNOWN",
            "A confirmed positive programme floor count is required",
        )
    floors = floors_raw

    target_gfa = _finite(program.get("target_gfa_m2"), "program.target_gfa_m2", positive=True)
    actual_gfa = _finite(design_metrics.get("gross_floor_area_m2"), "alternative.gross_floor_area_m2", positive=True)
    floor_count = design_parameters.get("floor_count")
    if isinstance(floor_count, bool) or not isinstance(floor_count, int) or floor_count != floors:
        raise SpatialLayoutError(
            "LAYOUT_FLOOR_COUNT_MISMATCH",
            "The selected concept floor count must match the reviewed programme",
            {"program_floor_count": floors, "alternative_floor_count": floor_count},
        )
    width = _finite(design_parameters.get("footprint_width_m"), "alternative.footprint_width_m", positive=True)
    depth = _finite(design_parameters.get("footprint_depth_m"), "alternative.footprint_depth_m", positive=True)
    floor_height = _finite(
        design_parameters.get("floor_to_floor_height_m"),
        "alternative.floor_to_floor_height_m",
        positive=True,
    )
    footprint_area = width * depth
    floor_area = actual_gfa / floors
    maximum_footprint = envelope.get("max_footprint_m2")
    maximum_gfa = envelope.get("max_gfa_m2")
    maximum_height = envelope.get("max_height_m")
    building_height = _finite(design_metrics.get("building_height_m"), "alternative.building_height_m", positive=True)
    if (
        maximum_footprint is not None
        and footprint_area > _finite(maximum_footprint, "envelope.max_footprint_m2") + _TOLERANCE_M
    ):
        raise SpatialLayoutError(
            "LAYOUT_MAX_FOOTPRINT_EXCEEDED",
            "Selected concept exceeds the current maximum footprint",
        )
    if maximum_gfa is not None and actual_gfa > _finite(maximum_gfa, "envelope.max_gfa_m2") + _TOLERANCE_M:
        raise SpatialLayoutError("LAYOUT_MAX_GFA_EXCEEDED", "Selected concept exceeds the current maximum GFA")
    if (
        maximum_height is not None
        and building_height > _finite(maximum_height, "envelope.max_height_m") + _TOLERANCE_M
    ):
        raise SpatialLayoutError("LAYOUT_MAX_HEIGHT_EXCEEDED", "Selected concept exceeds the current maximum height")
    if abs(footprint_area - floor_area) > max(0.02, floor_area * 1e-4):
        raise SpatialLayoutError(
            "LAYOUT_FOOTPRINT_AREA_MISMATCH",
            "Selected concept footprint area does not reconcile to its gross floor area and floor count",
            {"footprint_area_m2": round(footprint_area, 3), "required_floor_area_m2": round(floor_area, 3)},
        )

    normalized_spaces: list[dict[str, Any]] = []
    target_total = 0.0
    for index, item in enumerate(spaces):
        if not isinstance(item, dict):
            raise SpatialLayoutError(
                "LAYOUT_PROGRAM_INVALID",
                "Every programme space must be an object",
                {"index": index},
            )
        space_id = item.get("id")
        quantity = item.get("quantity", 1)
        if not isinstance(space_id, str) or not space_id:
            raise SpatialLayoutError(
                "LAYOUT_PROGRAM_INVALID",
                "Every programme space requires a stable ID",
                {"index": index},
            )
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise SpatialLayoutError(
                "LAYOUT_PROGRAM_INVALID",
                "Programme space quantity must be a positive integer",
                {"space_id": space_id},
            )
        target = _finite(item.get("target_area_m2"), f"spaces[{index}].target_area_m2", positive=True)
        minimum = _finite(item.get("min_area_m2"), f"spaces[{index}].min_area_m2", positive=True)
        maximum = _finite(item.get("max_area_m2"), f"spaces[{index}].max_area_m2", positive=True)
        if not minimum <= target <= maximum:
            raise SpatialLayoutError(
                "LAYOUT_PROGRAM_BOUNDS_INVALID",
                "Programme target must be within its declared area bounds",
                {"space_id": space_id},
            )
        target_total += target * quantity
        normalized_spaces.append({
            "id": space_id,
            "name": str(item.get("name") or item.get("space_type") or space_id),
            "space_type": str(item.get("space_type") or "unspecified"),
            "category": item.get("category"),
            "quantity": quantity,
            "target_area_m2": target,
            "min_area_m2": minimum,
            "max_area_m2": maximum,
        })

    if abs(target_total - target_gfa) > 0.02:
        raise SpatialLayoutError(
            "LAYOUT_PROGRAM_GFA_MISMATCH",
            "Programme space areas do not reconcile to the programme target GFA",
            {"space_area_total_m2": round(target_total, 3), "target_gfa_m2": round(target_gfa, 3)},
        )

    scale = actual_gfa / target_gfa
    for item in normalized_spaces:
        item["allocated_area_per_floor_m2"] = item["target_area_m2"] * scale / floors
        item["minimum_area_per_floor_m2"] = item["min_area_m2"] * scale / floors
        item["maximum_area_per_floor_m2"] = item["max_area_m2"] * scale / floors
        if not (
            item["minimum_area_per_floor_m2"] - 1e-6
            <= item["allocated_area_per_floor_m2"]
            <= item["maximum_area_per_floor_m2"] + 1e-6
        ):
            raise SpatialLayoutError(
                "LAYOUT_PROGRAM_BOUNDS_EXCEEDED",
                "The selected concept GFA would move a programme space outside its allowed area range",
                {"space_id": item["id"], "allocated_area_m2": item["allocated_area_per_floor_m2"]},
            )

    buildable_geojson = envelope.get("buildable_polygon")
    if not isinstance(buildable_geojson, dict):
        raise SpatialLayoutError("LAYOUT_ENVELOPE_INVALID", "The planning envelope has no buildable polygon")
    buildable, _ = _local_polygon(buildable_geojson)
    if buildable.area + _TOLERANCE_M < footprint_area:
        raise SpatialLayoutError(
            "LAYOUT_FOOTPRINT_EXCEEDS_ENVELOPE",
            "The selected concept footprint is larger than the buildable envelope",
            {"footprint_area_m2": round(footprint_area, 3), "buildable_area_m2": round(buildable.area, 3)},
        )

    rotation_raw = design_parameters.get("orientation_degrees")
    if rotation_raw is None:
        rotation_raw = design_parameters.get("rotation_deg")
    orientation_was_explicit = rotation_raw is not None
    rotation_degrees = _finite(0.0 if rotation_raw is None else rotation_raw, "alternative.orientation_degrees")
    translation = design_parameters.get("translation_m") or {}
    if not isinstance(translation, dict):
        raise SpatialLayoutError("LAYOUT_INPUT_INVALID", "Building translation must be a vector object")
    translation_x = _finite(translation.get("x", 0.0), "alternative.translation_m.x")
    translation_y = _finite(translation.get("y", 0.0), "alternative.translation_m.y")
    footprint, centre = _fit_footprint(
        buildable,
        width,
        depth,
        rotation_degrees,
        translation_x,
        translation_y,
    )

    adjacency_edges = program.get("adjacencies", [])
    if not isinstance(adjacency_edges, list):
        raise SpatialLayoutError("LAYOUT_PROGRAM_INVALID", "Programme adjacencies must be a list")

    floor_plates: list[dict[str, Any]] = []
    layout_spaces: list[dict[str, Any]] = []
    space_polygons: dict[str, Polygon] = {}
    floor_instance_ids: dict[int, dict[str, list[str]]] = {}
    for floor_number in range(1, floors + 1):
        floor_z = (floor_number - 1) * floor_height
        floor_plates.append({
            "id": str(
                uuid5(
                    NAMESPACE_URL,
                    f"airchitect:floor-plate:{project_version_id}:{floor_number}:{world_model_hash}",
                )
            ),
            "level_number": floor_number,
            "elevation_m": round(floor_z, 6),
            "area_m2": round(footprint_area, 6),
            "boundary": _transform_ring(
                ((-width / 2, -depth / 2), (width / 2, -depth / 2), (width / 2, depth / 2),
                 (-width / 2, depth / 2), (-width / 2, -depth / 2)),
                centre=centre,
                rotation_degrees=rotation_degrees,
                elevation_m=floor_z,
            ),
        })
        instances: list[dict[str, Any]] = []
        ids_by_program: dict[str, list[str]] = {}
        for item in normalized_spaces:
            for instance_number in range(1, item["quantity"] + 1):
                instance_id = str(uuid5(
                    NAMESPACE_URL,
                    (
                        f"airchitect:layout-space:{project_id}:{project_version_id}:"
                        f"{item['id']}:{floor_number}:{instance_number}"
                    ),
                ))
                ids_by_program.setdefault(item["id"], []).append(instance_id)
                instances.append({
                    **item,
                    "instance_id": instance_id,
                    "instance_number": instance_number,
                    "level_number": floor_number,
                    "area_m2": item["allocated_area_per_floor_m2"],
                })
        floor_instance_ids[floor_number] = ids_by_program
        ordered = _space_order(instances, adjacency_edges)
        cursor = -depth / 2 if width >= depth else -width / 2
        for item in ordered:
            area = float(item["area_m2"])
            if width >= depth:
                strip_depth = area / width
                local_bounds = ((-width / 2, cursor), (width / 2, cursor),
                                (width / 2, cursor + strip_depth), (-width / 2, cursor + strip_depth))
                cursor += strip_depth
            else:
                strip_width = area / depth
                local_bounds = ((cursor, -depth / 2), (cursor + strip_width, -depth / 2),
                                (cursor + strip_width, depth / 2), (cursor, depth / 2))
                cursor += strip_width
            world_ring = _transform_ring(
                (*local_bounds, local_bounds[0]),
                centre=centre,
                rotation_degrees=rotation_degrees,
                elevation_m=floor_z,
            )
            polygon = Polygon([(point[0], point[1]) for point in world_ring[:-1]])
            if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
                raise SpatialLayoutError(
                    "LAYOUT_SPACE_GEOMETRY_INVALID",
                    "A generated space boundary is invalid",
                    {"space_id": item["instance_id"]},
                )
            if not footprint.buffer(_TOLERANCE_M).covers(polygon):
                raise SpatialLayoutError(
                    "LAYOUT_SPACE_OUTSIDE_FOOTPRINT",
                    "A generated space falls outside its floor plate",
                    {"space_id": item["instance_id"]},
                )
            space_polygons[item["instance_id"]] = polygon
            layout_spaces.append({
                "id": item["instance_id"],
                "program_space_id": item["id"],
                "name": item["name"] if item["quantity"] == 1 else f"{item['name']} {item['instance_number']}",
                "space_type": item["space_type"],
                "category": item["category"],
                "level_number": floor_number,
                "area_m2": round(polygon.area, 6),
                "target_area_m2": round(item["target_area_m2"] / floors, 6),
                "allowed_area_m2": {
                    "minimum": round(item["minimum_area_per_floor_m2"], 6),
                    "maximum": round(item["maximum_area_per_floor_m2"], 6),
                },
                "boundary": world_ring,
                "centroid": [round(polygon.centroid.x, 6), round(polygon.centroid.y, 6)],
                "provenance": {
                    "program_artifact_hash": _canonical_hash(program),
                    "program_space_id": item["id"],
                    "allocation_method": "even_distribution_across_confirmed_storeys",
                },
                "geometry_status": "DERIVED_PRELIMINARY",
            })
        end_cursor = depth / 2 if width >= depth else width / 2
        axis_length = depth if width >= depth else width
        if abs(cursor - end_cursor) > max(0.02, axis_length * 1e-4):
            raise SpatialLayoutError(
                "LAYOUT_AREA_RECONCILIATION_FAILED",
                "Generated room partitions do not cover the selected floor plate",
            )

    adjacency_results: list[dict[str, Any]] = []
    unknowns = [
        "circulation_network",
        "door_opening_locations",
        "egress_routes",
        "vertical_connectivity",
        "room_accessibility",
    ]
    for edge in adjacency_edges:
        first_id, second_id = edge.get("from"), edge.get("to")
        if not isinstance(first_id, str) or not isinstance(second_id, str):
            raise SpatialLayoutError("LAYOUT_PROGRAM_INVALID", "Adjacency endpoints must be space IDs")
        relation = str(edge.get("relationship") or "")
        for floor_number in range(1, floors + 1):
            first_ids = floor_instance_ids[floor_number].get(first_id, [])
            second_ids = floor_instance_ids[floor_number].get(second_id, [])
            for first_space_id, second_space_id in zip(first_ids, second_ids):
                first_polygon, second_polygon = space_polygons[first_space_id], space_polygons[second_space_id]
                shared_length = first_polygon.boundary.intersection(second_polygon.boundary).length
                if relation in {"direct", "adjacent"}:
                    status = "SATISFIED" if shared_length > _TOLERANCE_M else "UNSATISFIED"
                elif relation == "near":
                    status = (
                        "SATISFIED"
                        if first_polygon.distance(second_polygon) <= 1.0 + _TOLERANCE_M
                        else "UNSATISFIED"
                    )
                elif relation == "separate":
                    status = "SATISFIED" if shared_length <= _TOLERANCE_M else "UNSATISFIED"
                else:
                    status = "DEFERRED_TO_TOPOLOGY"
                adjacency_results.append({
                    "from_space_id": first_space_id,
                    "to_space_id": second_space_id,
                    "relationship": relation,
                    "required": bool(edge.get("required", False)),
                    "status": status,
                    "shared_boundary_m": round(shared_length, 6),
                })

    unmet_required = [item for item in adjacency_results if item["required"] and item["status"] == "UNSATISFIED"]
    deferred_required = [
        item for item in adjacency_results
        if item["required"] and item["status"] == "DEFERRED_TO_TOPOLOGY"
    ]
    assumptions = [
        "Programme area targets are distributed evenly across the confirmed storeys.",
        "Each space is represented as a deterministic rectangular area partition; "
        "room-specific proportions and furniture clearances are not inferred.",
        "The selected concept footprint is placed at the nearest deterministic fit "
        "within the current buildable polygon.",
        "This layout is preliminary and requires architectural review before downstream use.",
    ]
    if not orientation_was_explicit:
        assumptions.append("No explicit building orientation was supplied; the local Cartesian X axis is used.")
    if unmet_required or deferred_required:
        unknowns.append("required_program_adjacencies")
    payload = {
        "schema_version": "phase3-spatial-layout-v1",
        "engine_version": ENGINE_VERSION,
        "coordinate_system": _COORDINATE_SYSTEM,
        "units": "m",
        "status": "REVIEW_REQUIRED" if unknowns or unmet_required or deferred_required else "PRELIMINARY",
        "project_id": project_id,
        "project_version_id": project_version_id,
        "world_model_hash": world_model_hash,
        "selected_alternative_id": alternative_id,
        "program_hash": _canonical_hash(program),
        "envelope_hash": _canonical_hash(envelope),
        "footprint": {
            "width_m": width,
            "depth_m": depth,
            "area_m2": round(footprint.area, 6),
            "orientation_degrees": rotation_degrees,
            "centre_m": [round(centre[0], 6), round(centre[1], 6)],
            "boundary": [[round(x, 6), round(y, 6)] for x, y in list(footprint.exterior.coords)],
        },
        "floor_plates": floor_plates,
        "spaces": layout_spaces,
        "adjacencies": adjacency_results,
        "area_reconciliation": {
            "target_gfa_m2": round(target_gfa, 6),
            "selected_concept_gfa_m2": round(actual_gfa, 6),
            "allocated_space_area_m2": round(sum(item["area_m2"] for item in layout_spaces), 6),
            "floor_plate_area_total_m2": round(sum(item["area_m2"] for item in floor_plates), 6),
            "reconciled": (
                abs(sum(item["area_m2"] for item in layout_spaces) - actual_gfa)
                <= max(0.02, actual_gfa * 1e-4)
            ),
        },
        "assumptions": assumptions,
        "unknowns": sorted(set(unknowns)),
        "source_lineage": {
            "world_model_hash": world_model_hash,
            "program_hash": _canonical_hash(program),
            "envelope_hash": _canonical_hash(envelope),
            "envelope_source_lineage": envelope.get("source_lineage") or {},
            "design_hash": design_metrics.get("design_hash"),
            "alternative_id": alternative_id,
        },
    }
    payload["layout_hash"] = _canonical_hash(payload)
    return payload


__all__ = ["ENGINE_VERSION", "SpatialLayoutError", "build_spatial_layout"]
