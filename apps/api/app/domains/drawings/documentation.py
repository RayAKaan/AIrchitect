from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from shapely.geometry import Polygon

from app.domains.model import ArchitecturalModel, model_hash


ENGINE_VERSION = "drawing-documentation-v1.0.0"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def build_drawing_documentation(model: ArchitecturalModel, drawing_package: dict[str, Any]) -> dict[str, Any]:
    """Add measured dimensions, schedules, legends and sheet references without guessing."""
    expected_hash = drawing_package.get("drawing_hash")
    source = dict(drawing_package)
    source.pop("drawing_hash", None)
    if not isinstance(expected_hash, str) or _digest(source) != expected_hash:
        raise ValueError("DRAWING_PACKAGE_HASH_INVALID")
    source_hash = model_hash(model)
    if drawing_package.get("source_model_hash") != source_hash:
        raise ValueError("DRAWING_PACKAGE_MODEL_MISMATCH")

    dimensions: list[dict[str, Any]] = []
    for wall in sorted(model.walls, key=lambda item: item.id):
        length = math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)
        dimensions.extend([
            {"id": f"{wall.id}:length", "element_id": wall.id, "property": "length",
             "value": round(length, 6), "unit": "m", "source": "canonical_wall_axis"},
            {"id": f"{wall.id}:height", "element_id": wall.id, "property": "height",
             "value": wall.height_m, "unit": "m", "source": "canonical_wall_parameter"},
            {"id": f"{wall.id}:thickness", "element_id": wall.id, "property": "thickness",
             "value": wall.thickness_m, "unit": "m", "source": "canonical_wall_parameter"},
        ])
    for opening in sorted((*model.doors, *model.windows), key=lambda item: item.id):
        dimensions.extend([
            {"id": f"{opening.id}:width", "element_id": opening.id, "property": "width",
             "value": opening.width_m, "unit": "m", "source": "canonical_opening_parameter"},
            {"id": f"{opening.id}:height", "element_id": opening.id, "property": "height",
             "value": opening.height_m, "unit": "m", "source": "canonical_opening_parameter"},
            {"id": f"{opening.id}:sill", "element_id": opening.id, "property": "sill_height",
             "value": opening.sill_height_m, "unit": "m", "source": "canonical_opening_parameter"},
        ])

    space_schedule = []
    for space in sorted(model.spaces, key=lambda item: item.id):
        polygon = Polygon([(point.x, point.y) for point in space.boundary])
        if not polygon.is_valid or polygon.area <= 0:
            raise ValueError(f"DRAWING_SPACE_BOUNDARY_INVALID:{space.id}")
        space_schedule.append({
            "element_id": space.id, "name": space.name, "level_id": space.level_id,
            "area_m2": round(polygon.area, 6), "minimum_area_m2": space.min_area_m2,
            "area_status": "MEETS_MINIMUM" if polygon.area + 1e-6 >= space.min_area_m2 else "BELOW_MINIMUM",
        })

    schedules = {
        "spaces": space_schedule,
        "walls": [{
            "element_id": item.id, "name": item.name, "level_id": item.level_id,
            "length_m": round(math.hypot(item.end.x - item.start.x, item.end.y - item.start.y), 6),
            "height_m": item.height_m, "thickness_m": item.thickness_m,
        } for item in sorted(model.walls, key=lambda item: item.id)],
        "doors": [{
            "element_id": item.id, "name": item.name, "level_id": item.level_id,
            "host_wall_id": item.host_wall_id, "width_m": item.width_m,
            "height_m": item.height_m, "sill_height_m": item.sill_height_m,
        } for item in sorted(model.doors, key=lambda item: item.id)],
        "windows": [{
            "element_id": item.id, "name": item.name, "level_id": item.level_id,
            "host_wall_id": item.host_wall_id, "width_m": item.width_m,
            "height_m": item.height_m, "sill_height_m": item.sill_height_m,
        } for item in sorted(model.windows, key=lambda item: item.id)],
        "slabs": [{
            "element_id": item.id, "name": item.name, "level_id": item.level_id,
            "area_m2": round(Polygon([(p.x, p.y) for p in item.boundary]).area, 6),
            "thickness_m": item.thickness_m,
        } for item in sorted(model.slabs, key=lambda item: item.id)],
    }
    layers = sorted({
        primitive["layer"]
        for view in drawing_package.get("views", [])
        for primitive in view.get("primitives", [])
        if isinstance(primitive, dict) and isinstance(primitive.get("layer"), str)
    } | {
        primitive["layer"]
        for view in drawing_package.get("elevations", [])
        for primitive in view.get("primitives", [])
        if isinstance(primitive, dict) and isinstance(primitive.get("layer"), str)
    })
    payload = {
        "schema_version": "drawing-documentation-v1",
        "engine_version": ENGINE_VERSION,
        "source_model_hash": source_hash,
        "source_drawing_hash": expected_hash,
        "units": "m",
        "dimensions": dimensions,
        "schedules": schedules,
        "legend": [{"layer": layer, "description": layer.replace("A-", "").replace("_", " ").title()} for layer in layers],
        "sheets": [{
            "sheet_id": "A-001",
            "title": "Architectural plans and elevations",
            "view_ids": [view["id"] for view in drawing_package.get("views", [])]
                        + [view["id"] for view in drawing_package.get("elevations", [])],
            "issue_status": "REVIEW",
            "scale": None,
            "paper_size": None,
            "unknowns": ["sheet_scale_not_set", "paper_size_not_set", "professional_issue_approval_required"],
        }],
        "unknowns": ["true_cut_sections_not_available_from_current_drawing_package"],
    }
    payload["documentation_hash"] = _digest(payload)
    return payload


__all__ = ["ENGINE_VERSION", "build_drawing_documentation"]
