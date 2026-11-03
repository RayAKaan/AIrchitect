from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from app.domains.model import ArchitecturalModel, model_hash


ENGINE_VERSION = "canonical-drawings-v1.0.0"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _point(x: float, y: float) -> dict[str, float]:
    return {"x": round(float(x), 6), "y": round(float(y), 6)}


def _line(layer: str, start: tuple[float, float], end: tuple[float, float], element_id: str) -> dict[str, Any]:
    return {"kind": "LINE", "layer": layer, "element_id": element_id,
            "start": _point(*start), "end": _point(*end)}


def _polyline(layer: str, points: list[tuple[float, float]], element_id: str) -> dict[str, Any]:
    return {"kind": "POLYLINE", "layer": layer, "element_id": element_id,
            "points": [_point(*point) for point in points], "closed": True}


def _wall_opening_line(opening: Any, wall: Any) -> tuple[tuple[float, float], tuple[float, float]]:
    dx, dy = wall.end.x - wall.start.x, wall.end.y - wall.start.y
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        raise ValueError(f"DRAWING_WALL_ZERO_LENGTH:{wall.id}")
    ux, uy = dx / length, dy / length
    half = opening.width_m / 2
    cx = wall.start.x + ux * opening.offset_m
    cy = wall.start.y + uy * opening.offset_m
    return (cx - ux * half, cy - uy * half), (cx + ux * half, cy + uy * half)


def build_drawing_package(model: ArchitecturalModel) -> dict[str, Any]:
    """Compile canonical model geometry into deterministic, reviewable vector views."""
    source_hash = model_hash(model)
    walls = {wall.id: wall for wall in model.walls}
    plan: list[dict[str, Any]] = []
    elevations: list[dict[str, Any]] = []
    for space in sorted(model.spaces, key=lambda item: item.id):
        plan.append(_polyline("A-SPACE", [(p.x, p.y) for p in space.boundary], space.id))
    for slab in sorted(model.slabs, key=lambda item: item.id):
        plan.append(_polyline("A-SLAB", [(p.x, p.y) for p in slab.boundary], slab.id))
    for wall in sorted(model.walls, key=lambda item: item.id):
        dx, dy = wall.end.x - wall.start.x, wall.end.y - wall.start.y
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            raise ValueError(f"DRAWING_WALL_ZERO_LENGTH:{wall.id}")
        nx, ny = -dy / length * wall.thickness_m / 2, dx / length * wall.thickness_m / 2
        a = (wall.start.x + nx, wall.start.y + ny)
        b = (wall.end.x + nx, wall.end.y + ny)
        c = (wall.end.x - nx, wall.end.y - ny)
        d = (wall.start.x - nx, wall.start.y - ny)
        plan.append(_polyline("A-WALL", [a, b, c, d], wall.id))
        elevations.append({
            "kind": "RECTANGLE", "layer": "A-WALL", "element_id": wall.id,
            "start": _point(0.0, wall.start.z),
            "end": _point(length, wall.start.z + wall.height_m),
            "baseline": {"start": _point(0.0, wall.start.z), "end": _point(length, wall.start.z)},
        })
    for opening in sorted((*model.doors, *model.windows), key=lambda item: item.id):
        wall = walls.get(opening.host_wall_id)
        if wall is None:
            raise ValueError(f"DRAWING_OPENING_HOST_MISSING:{opening.id}")
        start, end = _wall_opening_line(opening, wall)
        plan.append(_line("A-DOOR" if opening.element_type == "door" else "A-WINDOW", start, end, opening.id))
        dx, dy = wall.end.x - wall.start.x, wall.end.y - wall.start.y
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        offset = opening.offset_m
        elevations.append({
            "kind": "RECTANGLE", "layer": "A-DOOR" if opening.element_type == "door" else "A-WINDOW",
            "element_id": opening.id,
            "start": _point(offset - opening.width_m / 2, wall.start.z + opening.sill_height_m),
            "end": _point(offset + opening.width_m / 2, wall.start.z + opening.sill_height_m + opening.height_m),
            "host_wall_id": wall.id,
        })
    levels = [{"id": level.id, "name": level.name, "elevation_m": level.elevation_m}
              for level in sorted(model.levels, key=lambda item: (item.elevation_m, item.id))]
    payload = {
        "schema_version": "canonical-drawing-package-v1",
        "engine_version": ENGINE_VERSION,
        "source_model_hash": source_hash,
        "units": "m",
        "coordinate_system": "local_cartesian_z_up",
        "views": [
            {"id": "plan", "kind": "PLAN", "level_id": level.id,
             "elevation_m": level.elevation_m, "primitives": [
                 primitive for primitive in plan
                 if primitive["element_id"] in {
                     item.id for item in (*model.spaces, *model.slabs, *model.walls, *model.doors, *model.windows)
                     if getattr(item, "level_id", None) in (None, level.id)
                 }
             ]}
            for level in levels
        ],
        "elevations": [{"id": "elevation-1", "kind": "ELEVATION", "primitives": elevations}],
        "sections": [],
        "unknowns": ["section_cut_geometry_not_requested", "dimensions_and_annotations_not_generated"],
    }
    payload["drawing_hash"] = _digest(payload)
    return payload


__all__ = ["ENGINE_VERSION", "build_drawing_package"]
