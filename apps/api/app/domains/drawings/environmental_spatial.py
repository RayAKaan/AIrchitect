from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from shapely.geometry import LineString, Polygon

from app.domains.model import ArchitecturalModel, model_hash


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _polygon(space: Any) -> Polygon:
    points = [(point.x, point.y) for point in space.boundary]
    polygon = Polygon(points)
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
        raise ValueError(f"Space {space.id} has invalid or zero-area boundary geometry")
    return polygon


def analyze_environmental_spatial_performance(model: ArchitecturalModel) -> dict[str, Any]:
    """Produce auditable geometric proxies without claiming physical simulation."""
    spaces = {space.id: space for space in model.spaces}
    polygons = {space_id: _polygon(space) for space_id, space in spaces.items()}
    walls = {wall.id: wall for wall in model.walls}
    openings = (*model.doors, *model.windows)
    windows_by_space: dict[str, float] = {space_id: 0.0 for space_id in spaces}
    wall_area_by_space: dict[str, float] = {space_id: 0.0 for space_id in spaces}
    opening_area_by_space: dict[str, float] = {space_id: 0.0 for space_id in spaces}
    for wall in model.walls:
        length = math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)
        area = length * wall.height_m
        for space_id in wall.space_ids:
            if space_id in wall_area_by_space:
                wall_area_by_space[space_id] += area
    for opening in openings:
        wall = walls.get(opening.host_wall_id)
        if wall is None:
            continue
        area = opening.width_m * opening.height_m
        for space_id in wall.space_ids:
            if space_id not in opening_area_by_space:
                continue
            opening_area_by_space[space_id] += area
            if opening in model.windows:
                windows_by_space[space_id] += area

    room_metrics = []
    for space_id, space in sorted(spaces.items()):
        polygon = polygons[space_id]
        compactness = (4.0 * math.pi * polygon.area / (polygon.length ** 2)) if polygon.length else 0.0
        room_metrics.append({
            "space_id": space_id,
            "level_id": space.level_id,
            "floor_area_m2": round(polygon.area, 6),
            "perimeter_m": round(polygon.length, 6),
            "shape_compactness": round(compactness, 6),
            "window_opening_area_m2": round(windows_by_space[space_id], 6),
            "window_to_floor_area_ratio": round(windows_by_space[space_id] / polygon.area, 6),
            "declared_wall_area_m2": round(wall_area_by_space[space_id], 6),
            "opening_area_m2": round(opening_area_by_space[space_id], 6),
            "daylight_illuminance": {"status": "UNKNOWN", "reason": "No climate, orientation or simulation inputs"},
        })

    adjacency = []
    ids = sorted(spaces)
    for index, source_id in enumerate(ids):
        for target_id in ids[index + 1:]:
            shared = polygons[source_id].boundary.intersection(polygons[target_id].boundary)
            if shared.is_empty or shared.length <= 1e-6:
                continue
            door_ids = sorted(
                opening.id for opening in model.doors
                if opening.host_wall_id in walls
                and {source_id, target_id}.issubset(set(walls[opening.host_wall_id].space_ids))
            )
            adjacency.append({
                "source_space_id": source_id,
                "target_space_id": target_id,
                "shared_boundary_m": round(shared.length, 6),
                "relationship": "SHARED_BOUNDARY",
                "traversable": False,
                "door_opening_ids": door_ids,
            })

    payload: dict[str, Any] = {
        "schema_version": "environmental-spatial-analysis-v1",
        "source_model_hash": model_hash(model),
        "units": "m",
        "coordinate_system": "local_cartesian_z_up",
        "room_metrics": room_metrics,
        "spatial_adjacency": {"shared_boundary_edges": adjacency},
        "environmental": {
            "daylight": {"status": "NOT_SIMULATED", "missing_inputs": ["climate", "orientation", "window optical properties", "simulation settings"]},
            "solar": {"status": "NOT_SIMULATED", "missing_inputs": ["location", "date/time", "orientation", "shading context"]},
            "thermal": {"status": "NOT_SIMULATED", "missing_inputs": ["envelope assemblies", "climate", "occupancy", "HVAC systems"]},
            "ventilation": {"status": "NOT_SIMULATED", "missing_inputs": ["operable opening data", "wind/climate", "airflow model"]},
            "energy": {"status": "NOT_SIMULATED", "missing_inputs": ["envelope", "systems", "occupancy", "weather file"]},
        },
        "limitations": [
            "Geometric metrics are descriptive proxies, not physical simulation results.",
            "Shared boundaries and door candidates do not establish accessible or traversable routes.",
        ],
    }
    payload["analysis_hash"] = _digest(payload)
    return payload
