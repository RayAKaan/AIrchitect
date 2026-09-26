from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel
from app.domains.design.config import DesignEngineConfig
from app.domains.design.constraints import DesignConstraint, ResolvedDesignContext


class DesignCandidate(BaseModel):
    candidate_key: str
    strategy_id: str
    strategy_version: str
    parameters: dict[str, Any]
    metrics: dict[str, float | int | None]
    constraint_results: list[dict[str, Any]]
    tradeoffs: list[dict[str, Any]]
    reasoning: dict[str, Any]
    assumptions: list[dict[str, Any]]
    unknowns: list[str]
    valid: bool
    invalid_reasons: list[str]
    score: float


class DesignStrategy(ABC):
    id: str
    version = "1.0"
    name: str
    description: str

    @abstractmethod
    def profiles(self) -> list[tuple[float, float, int]]: ...

    def generate_candidates(self, context: ResolvedDesignContext, config: DesignEngineConfig,
                            target_gfa: float, preferred_floors: int, floor_height: float,
                            parking_count: int | None) -> list[DesignCandidate]:
        variable = next(v for v in context.search_space.variables if v.name == "floor_count")
        output = []
        for index, (gfa_factor, aspect_ratio, floor_delta) in enumerate(self.profiles(), 1):
            floors = int(max(variable.min_value, min(variable.max_value, preferred_floors + floor_delta)))
            actual_gfa = target_gfa * gfa_factor
            footprint = actual_gfa / floors
            width = (footprint * aspect_ratio) ** .5
            depth = footprint / width
            params = {"floor_count": floors, "floor_to_floor_height_m": floor_height,
                "footprint_width_m": width, "footprint_depth_m": depth,
                "footprint_aspect_ratio": aspect_ratio, "core_ratio": config.default_core_ratio,
                "setback_m": _constraint_value(context.constraints, "setback", 0.0),
                "orientation_degrees": None}
            metrics = calculate_metrics(params, context, parking_count)
            results, reasons = validate_candidate(params, metrics, context.constraints, context, config)
            deviation = abs(float(metrics["gross_floor_area_m2"]) - target_gfa) / target_gfa if target_gfa else 0
            objective = self._objective(metrics, target_gfa)
            score = objective + deviation
            output.append(DesignCandidate(candidate_key=f"{self.id}-{index}", strategy_id=self.id,
                strategy_version=self.version, parameters=params, metrics=metrics,
                constraint_results=results, tradeoffs=self._tradeoffs(metrics, preferred_floors),
                reasoning=self._reasoning(metrics, target_gfa, preferred_floors),
                assumptions=context.search_space.assumptions, unknowns=context.search_space.unknowns,
                valid=not reasons, invalid_reasons=reasons, score=round(score, 8)))
        return output

    def _objective(self, metrics: dict[str, Any], target_gfa: float) -> float:
        return 0.0

    def _tradeoffs(self, metrics: dict[str, Any], preferred_floors: int) -> list[dict[str, Any]]:
        return [{"metric": "site_coverage", "value": metrics["site_coverage_ratio"],
                 "effect": "Lower coverage preserves more open site."},
                {"metric": "building_height", "value": metrics["building_height_m"],
                 "effect": "Height follows floor count and floor-to-floor parameter."},
                {"metric": "floor_count_deviation", "value": int(metrics["floor_count"]) - preferred_floors,
                 "effect": "Zero means the preferred floor count is retained."}]

    def _reasoning(self, metrics: dict[str, Any], target_gfa: float, preferred_floors: int) -> dict[str, Any]:
        return {"strategy": self.id, "strategy_name": self.name, "purpose": self.description,
            "primary_objective": self.primary_objective(), "key_result": self.key_result(metrics),
            "target_gfa_m2": target_gfa, "actual_gfa_m2": metrics["gross_floor_area_m2"],
            "gfa_deviation_percent": round((float(metrics["gross_floor_area_m2"]) - target_gfa) / target_gfa * 100, 3) if target_gfa else None,
            "preferred_floor_count": preferred_floors, "actual_floor_count": metrics["floor_count"],
            "human_review_required": True, "safety_boundary": "Preliminary computational massing; not for construction."}

    @abstractmethod
    def primary_objective(self) -> str: ...

    @abstractmethod
    def key_result(self, metrics: dict[str, Any]) -> str: ...


class BalancedStrategy(DesignStrategy):
    id, name = "balanced", "Balanced"
    description = "Balance target GFA, site use, height and usable floor plates."
    def profiles(self): return [(1.0, 1.0, 0), (.98, 1.10, 0), (1.02, .90, 0)]
    def _objective(self, metrics, target_gfa): return abs(float(metrics["site_coverage_ratio"]) - .55)
    def primary_objective(self): return "Balance GFA fidelity, coverage and massing proportions."
    def key_result(self, metrics): return f"{float(metrics['site_coverage_ratio'])*100:.1f}% site coverage with balanced proportions."


class CompactStrategy(DesignStrategy):
    id, name = "compact", "Compact"
    description = "Reduce footprint and preserve open site, accepting verticality where floor count is flexible."
    def profiles(self): return [(.94, .78, 1), (.96, .85, 1), (.98, .70, 1)]
    def _objective(self, metrics, target_gfa): return float(metrics["site_coverage_ratio"])
    def primary_objective(self): return "Minimize footprint and site coverage within known constraints."
    def key_result(self, metrics): return f"{float(metrics['open_site_area_m2']):,.0f} m² open site remains."


class LowRiseStrategy(DesignStrategy):
    id, name = "low_rise", "Low-Rise"
    description = "Reduce vertical stacking and use a broader floor plate where constraints permit."
    def profiles(self): return [(1.0, 1.35, -1), (1.03, 1.50, -1), (.97, 1.20, 0)]
    def _objective(self, metrics, target_gfa): return float(metrics["building_height_m"]) / 100
    def primary_objective(self): return "Minimize building height within site and coverage constraints."
    def key_result(self, metrics): return f"{float(metrics['building_height_m']):.1f} m conceptual building height."


STRATEGIES: tuple[DesignStrategy, ...] = (BalancedStrategy(), CompactStrategy(), LowRiseStrategy())


def calculate_metrics(params: dict[str, Any], context: ResolvedDesignContext,
                      parking_count: int | None) -> dict[str, float | int | None]:
    width, depth = float(params["footprint_width_m"]), float(params["footprint_depth_m"])
    footprint = width * depth; floors = int(params["floor_count"]); floor_height = float(params["floor_to_floor_height_m"])
    site_area = context.search_space.site_width_m * context.search_space.site_depth_m
    gfa = footprint * floors; core_area = footprint * float(params["core_ratio"])
    return {"site_area_m2": round(site_area, 6), "building_footprint_m2": round(footprint, 6),
        "site_coverage_ratio": round(footprint / site_area, 8) if site_area else 0,
        "floor_count": floors, "floor_to_floor_height_m": floor_height,
        "building_height_m": round(floors * floor_height, 6), "gross_floor_area_m2": round(gfa, 6),
        "building_volume_m3": round(gfa * floor_height, 6), "open_site_area_m2": round(site_area - footprint, 6),
        "core_area_per_floor_m2": round(core_area, 6), "net_area_m2": round(gfa - core_area * floors, 6),
        "efficiency_ratio": round(1 - float(params["core_ratio"]), 6), "parking_count": parking_count}


def validate_candidate(params: dict[str, Any], metrics: dict[str, Any], constraints: list[DesignConstraint],
                       context: ResolvedDesignContext, config: DesignEngineConfig) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []; failures: list[str] = []
    actuals = {"site_area": metrics["site_area_m2"], "floor_count": metrics["floor_count"],
        "target_gfa": metrics["gross_floor_area_m2"], "floor_to_floor_height": metrics["floor_to_floor_height_m"],
        "max_coverage": metrics["site_coverage_ratio"], "setback": params["setback_m"],
        "max_height": metrics["building_height_m"], "parking_spaces": metrics["parking_count"]}
    for constraint in constraints:
        actual = actuals.get(constraint.parameter)
        if constraint.classification == "UNKNOWN":
            status, deviation = "UNKNOWN", None
        elif constraint.parameter == "target_gfa":
            deviation = (float(actual) - float(constraint.value)) / float(constraint.value) if constraint.value else None
            status = "PASS" if deviation is not None and abs(deviation) <= config.gfa_tolerance_ratio else "DEVIATION"
        else:
            status = _evaluate(constraint.operator, actual, constraint.value)
            deviation = None
        result = {"parameter": constraint.parameter, "classification": constraint.classification,
            "status": status, "actual": actual, "required": constraint.value, "unit": constraint.unit,
            "deviation": deviation, "source_reference": constraint.source_reference, "rationale": constraint.rationale}
        results.append(result)
        if constraint.classification == "HARD" and status != "PASS": failures.append(f"{constraint.parameter}:{status}")
    setback = float(params["setback_m"]); available_w = context.search_space.site_width_m - 2 * setback
    available_d = context.search_space.site_depth_m - 2 * setback
    if float(params["footprint_width_m"]) > available_w + 1e-6 or float(params["footprint_depth_m"]) > available_d + 1e-6:
        failures.append("building_outside_site")
    if float(metrics["building_footprint_m2"]) < config.minimum_floor_plate_m2: failures.append("floor_plate_below_minimum")
    if float(metrics["open_site_area_m2"]) < -1e-6: failures.append("negative_open_site")
    return results, sorted(set(failures))


def _evaluate(operator: str, actual: Any, required: Any) -> str:
    if actual is None or required is None: return "UNKNOWN"
    if operator == "eq": return "PASS" if actual == required else "FAIL"
    if operator == "lte": return "PASS" if float(actual) <= float(required) else "FAIL"
    if operator == "gte": return "PASS" if float(actual) >= float(required) else "FAIL"
    if operator == "exists": return "PASS" if actual is not None else "UNKNOWN"
    return "UNKNOWN"


def _constraint_value(constraints: list[DesignConstraint], parameter: str, default: float) -> float:
    item = next((c for c in constraints if c.parameter == parameter and c.value is not None), None)
    return float(item.value) if item else default
