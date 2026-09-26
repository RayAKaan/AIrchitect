from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel
from app.domains.design.config import DesignEngineConfig

ConstraintClass = Literal["HARD", "PREFERRED", "FLEXIBLE", "UNKNOWN"]


class DesignConstraint(BaseModel):
    parameter: str
    value: Any = None
    unit: str | None = None
    classification: ConstraintClass
    operator: str
    severity: str
    source_reference: str
    rationale: str
    provenance: dict[str, Any]


class DesignVariable(BaseModel):
    name: str
    min_value: float
    max_value: float
    preferred_value: float
    step: float
    unit: str
    source: str
    classification: ConstraintClass


class DesignSearchSpace(BaseModel):
    variables: list[DesignVariable]
    site_width_m: float
    site_depth_m: float
    site_boundary_source: str
    assumptions: list[dict[str, Any]]
    unknowns: list[str]


class ResolvedDesignContext(BaseModel):
    constraints: list[DesignConstraint]
    search_space: DesignSearchSpace
    conflicts: list[dict[str, Any]]


class DesignConstraintResolver:
    def __init__(self, config: DesignEngineConfig):
        self.config = config

    def resolve(self, model: dict[str, Any], world_model_hash: str) -> ResolvedDesignContext:
        constraints: list[DesignConstraint] = []
        assumptions: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        provenance = model.get("provenance", {})
        site = model.get("site", {})
        building = model.get("building", {})
        parking = model.get("parking", {})
        properties = model.get("properties", {})
        unknowns = list(model.get("unknowns", []))

        def add(parameter: str, value: Any, unit: str | None, classification: ConstraintClass,
                operator: str, rationale: str, source: str, severity: str = "ERROR") -> None:
            constraints.append(DesignConstraint(parameter=parameter, value=value, unit=unit,
                classification=classification, operator=operator, severity=severity,
                source_reference=source, rationale=rationale,
                provenance={"world_model_hash": world_model_hash, "source": source}))

        site_area = _quantity(site.get("area"))
        if site_area is None or site_area <= 0:
            add("site_area", None, "m2", "UNKNOWN", "exists", "A positive site area is required for bounded geometry.",
                "world_model:site.area")
            conflicts.append({"code": "SITE_AREA_REQUIRED", "message": "A positive canonical site area is required."})
        else:
            add("site_area", site_area, "m2", "HARD", "eq", "Geometry and coverage must use the canonical site area.",
                _source(provenance, "site_area", "world_model:site.area"))

        floor_count = building.get("floor_count")
        floor_prov = provenance.get("floor_count", {})
        if floor_count is None:
            preferred_floors = self.config.default_floor_count
            assumptions.append(_default("floor_count", preferred_floors, "count", self.config.config_version,
                "Canonical floor count is unknown; explored as a design variable."))
            add("floor_count", None, "count", "UNKNOWN", "exists", "Canonical floor count is unknown.", "world_model:unknown")
            floor_class: ConstraintClass = "FLEXIBLE"
        else:
            preferred_floors = int(floor_count)
            floor_class = "HARD" if floor_prov.get("confirmed") else "PREFERRED"
            add("floor_count", preferred_floors, "count", floor_class, "eq",
                "Confirmed user floor count is fixed; unconfirmed count is a preferred target.",
                _source(provenance, "floor_count", "world_model:building.floor_count"),
                "ERROR" if floor_class == "HARD" else "WARNING")

        target_gfa = _quantity(building.get("target_gfa"))
        if target_gfa is None:
            if site_area:
                target_gfa = site_area * self.config.default_target_coverage * preferred_floors
                assumptions.append(_default("target_gfa", target_gfa, "m2", self.config.config_version,
                    "Target GFA is unknown; provisional search target derives from site area, target coverage and floors."))
            add("target_gfa", None, "m2", "UNKNOWN", "exists", "Canonical target GFA is unknown.", "world_model:unknown", "INFO")
        else:
            add("target_gfa", target_gfa, "m2", "PREFERRED", "approximately",
                "Target GFA is optimized within the configured tolerance, not treated as exact geometry.",
                _source(provenance, "target_gfa", "world_model:building.target_gfa"), "WARNING")

        floor_height = _quantity(building.get("floor_to_floor_height"))
        if floor_height is None:
            floor_height = self.config.default_floor_height_m
            assumptions.append(_default("floor_to_floor_height", floor_height, "m", self.config.config_version,
                "Canonical floor height is unknown; engine default is an explicit design parameter."))
            add("floor_to_floor_height", None, "m", "UNKNOWN", "exists", "Canonical floor height is unknown.",
                "world_model:unknown", "INFO")
        else:
            add("floor_to_floor_height", floor_height, "m", "PREFERRED", "approximately",
                "Accepted preliminary floor height is used as the preferred design parameter.",
                _source(provenance, "floor_to_floor_height", "world_model:building.floor_to_floor_height"), "WARNING")

        max_coverage = float(properties.get("max_coverage", self.config.default_max_coverage))
        coverage_source = "world_model:properties.max_coverage" if "max_coverage" in properties else f"engine_default:{self.config.config_version}"
        add("max_coverage", max_coverage, "ratio", "HARD", "lte",
            "Building footprint may not exceed this design constraint. Engine default is not a regulation.", coverage_source)
        if not 0 < max_coverage <= 1:
            conflicts.append({"code": "INVALID_MAX_COVERAGE", "value": max_coverage})

        setback = float(properties.get("setback_m", self.config.default_setback_m))
        add("setback", setback, "m", "HARD" if "setback_m" in properties else "FLEXIBLE", "gte",
            "Canonical setback when supplied; otherwise an explicit zero design-engine default, not a regulation.",
            "world_model:properties.setback_m" if "setback_m" in properties else f"engine_default:{self.config.config_version}")

        max_height = properties.get("max_height_m")
        if max_height is None:
            add("max_height", None, "m", "UNKNOWN", "exists", "No canonical maximum height is available.", "world_model:unknown", "INFO")
        else:
            add("max_height", float(max_height), "m", "HARD", "lte", "Canonical maximum design height.",
                "world_model:properties.max_height_m")

        parking_count = _quantity(parking.get("spaces"))
        if parking_count is None:
            add("parking_spaces", None, "count", "UNKNOWN", "exists",
                "Parking capacity is not known; no parking layout is fabricated.", "world_model:unknown", "INFO")
        else:
            parking_class: ConstraintClass = "HARD" if provenance.get("parking_spaces", {}).get("confirmed") else "PREFERRED"
            add("parking_spaces", int(parking_count), "count", parking_class, "gte",
                "Capacity metric only; Phase 2 does not claim a complete parking layout.",
                _source(provenance, "parking_spaces", "world_model:parking.spaces"),
                "ERROR" if parking_class == "HARD" else "WARNING")

        width = _quantity(site.get("width")); depth = _quantity(site.get("depth"))
        boundary = site.get("boundary")
        if boundary and len(boundary) >= 3:
            xs, ys = [float(p[0]) for p in boundary], [float(p[1]) for p in boundary]
            site_width, site_depth = max(xs) - min(xs), max(ys) - min(ys)
            boundary_source = "canonical_polygon_bounding_box"
            # Only rectangular polygons are currently supported.
            if len(set(xs)) > 2 or len(set(ys)) > 2:
                conflicts.append({"code": "UNSUPPORTED_SITE_TOPOLOGY", "message": "Phase 2 supports rectangular site boundaries only."})
        elif width and depth:
            site_width, site_depth, boundary_source = width, depth, "canonical_dimensions"
        elif site_area:
            aspect = self.config.default_site_aspect_ratio
            site_width = (site_area * aspect) ** .5; site_depth = site_area / site_width
            boundary_source = "derived_rectangular_approximation"
            assumptions.append(_default("site_boundary", {"width_m": site_width, "depth_m": site_depth}, "m",
                self.config.config_version, "Site boundary is unknown; a rectangular area-preserving approximation is used and labeled."))
        else:
            site_width = site_depth = 0.0; boundary_source = "unavailable"

        max_floor = preferred_floors if floor_class == "HARD" else min(self.config.maximum_floor_count, preferred_floors + 2)
        min_floor = preferred_floors if floor_class == "HARD" else max(self.config.minimum_floor_count, preferred_floors - 2)
        variables = [
            DesignVariable(name="floor_count", min_value=min_floor, max_value=max_floor,
                preferred_value=preferred_floors, step=1, unit="count", source="world_model_or_engine_default", classification=floor_class),
            DesignVariable(name="floor_to_floor_height", min_value=self.config.minimum_floor_height_m,
                max_value=self.config.maximum_floor_height_m, preferred_value=floor_height, step=.1, unit="m",
                source="world_model_or_engine_default", classification="FLEXIBLE"),
            DesignVariable(name="footprint_aspect_ratio", min_value=.65, max_value=1.55,
                preferred_value=1.0, step=.05, unit="ratio", source=f"engine_config:{self.config.config_version}", classification="FLEXIBLE"),
            DesignVariable(name="core_ratio", min_value=.08, max_value=.18,
                preferred_value=self.config.default_core_ratio, step=.01, unit="ratio",
                source=f"engine_config:{self.config.config_version}", classification="FLEXIBLE"),
        ]
        return ResolvedDesignContext(constraints=constraints,
            search_space=DesignSearchSpace(variables=variables, site_width_m=site_width, site_depth_m=site_depth,
                site_boundary_source=boundary_source, assumptions=assumptions, unknowns=unknowns), conflicts=conflicts)


def _quantity(value: Any) -> float | None:
    if value is None: return None
    if isinstance(value, dict):
        raw = value.get("value")
        return float(raw) if raw is not None else None
    return float(value)


def _source(provenance: dict[str, Any], key: str, fallback: str) -> str:
    value = provenance.get(key)
    return f"{value.get('source_type')}:{value.get('source_id')}" if value else fallback


def _default(parameter: str, value: Any, unit: str, config_version: str, reason: str) -> dict[str, Any]:
    return {"parameter": parameter, "value": value, "unit": unit, "classification": "DERIVED_DESIGN_PARAMETER",
        "source": f"design_engine_config:{config_version}", "reason": reason}
