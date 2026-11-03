from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from shapely.geometry import Polygon

from app.domains.model import ArchitecturalModel, model_hash


ENGINE_VERSION = "engineering-analysis-v1.0.0"


class UnitRate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    quantity_code: str = Field(min_length=1, max_length=80)
    rate: float = Field(ge=0, le=1_000_000_000)
    unit: str = Field(min_length=1, max_length=30)
    description: str = Field(min_length=1, max_length=200)


class CostSchedule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schedule_id: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=60)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source: str = Field(min_length=1, max_length=500)
    rates: tuple[UnitRate, ...] = Field(min_length=1, max_length=100)

    @field_validator("rates")
    @classmethod
    def unique_quantity_codes(cls, values: tuple[UnitRate, ...]) -> tuple[UnitRate, ...]:
        codes = [item.quantity_code for item in values]
        if len(codes) != len(set(codes)):
            raise ValueError("Cost schedule quantity codes must be unique")
        return values


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _space_polygon(space: Any) -> Polygon:
    polygon = Polygon([(point.x, point.y) for point in space.boundary])
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
        raise ValueError(f"SPACE_GEOMETRY_INVALID:{space.id}")
    return polygon


def _structural_concept(model: ArchitecturalModel, bounds: tuple[float, float, float, float]) -> dict[str, Any]:
    min_x, min_y, max_x, max_y = bounds
    width, depth = max_x - min_x, max_y - min_y
    max_bay = 8.0
    x_count = max(1, math.ceil(width / max_bay))
    y_count = max(1, math.ceil(depth / max_bay))
    x_axes = [round(min_x + width * index / x_count, 6) for index in range(x_count + 1)]
    y_axes = [round(min_y + depth * index / y_count, 6) for index in range(y_count + 1)]
    levels = sorted(model.levels, key=lambda item: (item.elevation_m, item.id))
    return {
        "status": "CONCEPT_ONLY",
        "system": "UNSPECIFIED",
        "grid": {"x_axes_m": x_axes, "y_axes_m": y_axes},
        "indicative_column_positions_per_level": len(x_axes) * len(y_axes),
        "indicative_beam_segments_per_level": (len(x_axes) - 1) * len(y_axes) + (len(y_axes) - 1) * len(x_axes),
        "level_count": len(levels),
        "building_height_m": round(max((level.elevation_m + level.height_m for level in levels), default=0.0), 6),
        "capacity_checks": {"gravity": "NOT_PERFORMED", "wind": "NOT_PERFORMED", "seismic": "NOT_PERFORMED", "foundation": "NOT_PERFORMED"},
        "missing_inputs": ["structural system", "member sections", "material grades", "design loads", "soil report", "wind and seismic parameters"],
        "limitations": ["Grid and member counts are indicative only; they are not a structural design.", "No member sizing, stability, foundation, wind, seismic or code calculations were performed."],
    }


def build_engineering_analysis(model: ArchitecturalModel, cost_schedule: CostSchedule | None = None) -> dict[str, Any]:
    """Derive measured geometry quantities and explicitly bounded engineering proxies."""
    model_digest = model_hash(model)
    space_polygons = {space.id: _space_polygon(space) for space in model.spaces}
    space_area = sum(polygon.area for polygon in space_polygons.values())
    if space_polygons:
        min_x = min(p.bounds[0] for p in space_polygons.values())
        min_y = min(p.bounds[1] for p in space_polygons.values())
        max_x = max(p.bounds[2] for p in space_polygons.values())
        max_y = max(p.bounds[3] for p in space_polygons.values())
    else:
        min_x, min_y = model.site.origin.x, model.site.origin.y
        max_x, max_y = min_x + model.site.width_m, min_y + model.site.depth_m

    wall_lines = []
    wall_volume = 0.0
    wall_area = 0.0
    for wall in sorted(model.walls, key=lambda item: item.id):
        length = math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)
        volume = length * wall.height_m * wall.thickness_m
        area = length * wall.height_m
        wall_volume += volume
        wall_area += area
        wall_lines.append({"element_id": wall.id, "length_m": round(length, 6),
                           "height_m": wall.height_m, "thickness_m": wall.thickness_m,
                           "gross_face_area_m2": round(area, 6), "gross_volume_m3": round(volume, 6),
                           "material": "UNSPECIFIED"})

    slab_lines = []
    slab_area = 0.0
    slab_volume = 0.0
    for slab in sorted(model.slabs, key=lambda item: item.id):
        polygon = Polygon([(point.x, point.y) for point in slab.boundary])
        if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
            raise ValueError(f"SLAB_GEOMETRY_INVALID:{slab.id}")
        area = polygon.area
        volume = area * slab.thickness_m
        slab_area += area
        slab_volume += volume
        slab_lines.append({"element_id": slab.id, "area_m2": round(area, 6),
                           "thickness_m": slab.thickness_m, "volume_m3": round(volume, 6),
                           "material": "UNSPECIFIED"})

    door_area = sum(item.width_m * item.height_m for item in model.doors)
    window_area = sum(item.width_m * item.height_m for item in model.windows)
    quantities = [
        {"code": "gross_space_floor_area", "quantity": round(space_area, 6), "unit": "m2", "basis": "sum_of_space_polygons"},
        {"code": "wall_gross_face_area", "quantity": round(wall_area, 6), "unit": "m2", "basis": "wall_axis_length_times_height"},
        {"code": "wall_volume", "quantity": round(wall_volume, 6), "unit": "m3", "basis": "wall_axis_length_times_height_times_thickness"},
        {"code": "slab_area", "quantity": round(slab_area, 6), "unit": "m2", "basis": "canonical_slab_polygon_area"},
        {"code": "slab_volume", "quantity": round(slab_volume, 6), "unit": "m3", "basis": "slab_polygon_area_times_thickness"},
        {"code": "door_opening_area", "quantity": round(door_area, 6), "unit": "m2", "basis": "sum_of_declared_door_width_times_height"},
        {"code": "window_opening_area", "quantity": round(window_area, 6), "unit": "m2", "basis": "sum_of_declared_window_width_times_height"},
        {"code": "door_count", "quantity": len(model.doors), "unit": "count", "basis": "canonical_door_elements"},
        {"code": "window_count", "quantity": len(model.windows), "unit": "count", "basis": "canonical_window_elements"},
    ]
    quantity_by_code = {item["code"]: item for item in quantities}
    cost = {"status": "NOT_ESTIMATED", "reason": "A versioned, sourced unit-rate schedule was not supplied."}
    if cost_schedule is not None:
        lines = []
        for rate in cost_schedule.rates:
            quantity = quantity_by_code.get(rate.quantity_code)
            if quantity is None:
                raise ValueError(f"COST_RATE_QUANTITY_UNKNOWN:{rate.quantity_code}")
            expected_unit = quantity["unit"]
            if rate.unit != expected_unit:
                raise ValueError(f"COST_RATE_UNIT_MISMATCH:{rate.quantity_code}:{expected_unit}:{rate.unit}")
            amount = round(float(quantity["quantity"]) * rate.rate, 2)
            lines.append({"quantity_code": rate.quantity_code, "description": rate.description,
                          "quantity": quantity["quantity"], "unit": rate.unit,
                          "unit_rate": rate.rate, "amount": amount, "currency": cost_schedule.currency})
        cost = {"status": "PRELIMINARY_USER_RATES", "schedule_id": cost_schedule.schedule_id,
                "schedule_version": cost_schedule.version, "schedule_source": cost_schedule.source,
                "currency": cost_schedule.currency, "lines": lines,
                "total": round(sum(item["amount"] for item in lines), 2),
                "limitations": ["Rates are user-supplied and are not independently verified.", "No taxes, preliminaries, contingency, escalation, procurement or location adjustments are included."]}

    payload: dict[str, Any] = {
        "schema_version": "engineering-analysis-v1",
        "engine_version": ENGINE_VERSION,
        "source_model_hash": model_digest,
        "units": "m",
        "structural": _structural_concept(model, (min_x, min_y, max_x, max_y)),
        "quantities": quantities,
        "element_schedules": {"walls": wall_lines, "slabs": slab_lines,
                              "doors": [{"element_id": item.id, "width_m": item.width_m, "height_m": item.height_m} for item in sorted(model.doors, key=lambda item: item.id)],
                              "windows": [{"element_id": item.id, "width_m": item.width_m, "height_m": item.height_m} for item in sorted(model.windows, key=lambda item: item.id)]},
        "materials": {"status": "UNSPECIFIED", "items": [
            {"element_id": item["element_id"], "element_type": "Wall", "material": "UNSPECIFIED"} for item in wall_lines
        ] + [
            {"element_id": item["element_id"], "element_type": "Slab", "material": "UNSPECIFIED"} for item in slab_lines
        ], "missing_inputs": ["material assignments", "grade/specification", "fire/acoustic/thermal performance", "finish systems"]},
        "cost": cost,
        "limitations": ["Quantities are geometric take-offs, not tender quantities; deductions, laps, waste and construction tolerances are excluded.",
                        "Material types and grades are not inferred from geometry.",
                        "Structural checks are not performed by this analysis."],
    }
    payload["analysis_hash"] = _digest(payload)
    return payload
