from __future__ import annotations

import math
from typing import Any

from app.domains.design.strategies import DesignCandidate


class S2DesignInputError(ValueError):
    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None):
        self.code = code
        self.context = context or {}
        super().__init__(message)


def _finite_number(value: Any, *, field: str, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise S2DesignInputError(
            "S2_INPUT_INVALID",
            f"{field} must be a finite number",
            {"field": field, "value": value},
        )
    return float(value)


def resolve_s2_design_inputs(program: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(program, dict) or not isinstance(envelope, dict):
        raise S2DesignInputError("S2_INPUT_INVALID", "Current programme and envelope payloads are required")

    target_gfa = _finite_number(program.get("target_gfa_m2"), field="program.target_gfa_m2")
    if target_gfa is None or target_gfa <= 0:
        raise S2DesignInputError("S2_PROGRAM_INVALID", "The architectural programme requires a positive target GFA")

    spaces = program.get("spaces")
    if not isinstance(spaces, list) or not spaces:
        raise S2DesignInputError("S2_PROGRAM_INVALID", "The architectural programme must contain at least one space")
    space_ids: set[str] = set()
    allocated_area = 0.0
    normalized_spaces = []
    for index, space in enumerate(spaces):
        if not isinstance(space, dict):
            raise S2DesignInputError("S2_PROGRAM_INVALID", "Every programme space must be an object", {"index": index})
        space_id = space.get("id")
        space_type = space.get("space_type")
        if not isinstance(space_id, str) or not space_id or space_id in space_ids:
            raise S2DesignInputError("S2_PROGRAM_INVALID", "Programme space IDs must be non-empty and unique", {"index": index})
        if not isinstance(space_type, str) or not space_type:
            raise S2DesignInputError("S2_PROGRAM_INVALID", "Every programme space requires a space type", {"space_id": space_id})
        quantity = space.get("quantity", 1)
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise S2DesignInputError("S2_PROGRAM_INVALID", "Programme space quantity must be a positive integer", {"space_id": space_id})
        area = _finite_number(space.get("target_area_m2"), field=f"spaces[{index}].target_area_m2")
        minimum = _finite_number(space.get("min_area_m2"), field=f"spaces[{index}].min_area_m2")
        maximum = _finite_number(space.get("max_area_m2"), field=f"spaces[{index}].max_area_m2")
        if area is None or minimum is None or maximum is None or minimum <= 0 or not minimum <= area <= maximum:
            raise S2DesignInputError(
                "S2_PROGRAM_INVALID",
                "Each programme space must have a positive area target within its allowed range",
                {"space_id": space_id, "minimum": minimum, "target": area, "maximum": maximum},
            )
        space_ids.add(space_id)
        allocated_area += area * quantity
        normalized_spaces.append({
            "id": space_id,
            "space_type": space_type,
            "quantity": quantity,
            "target_area_m2": area,
            "min_area_m2": minimum,
            "max_area_m2": maximum,
            "category": space.get("category"),
        })

    residual = target_gfa - allocated_area
    if abs(residual) > 0.02:
        raise S2DesignInputError(
            "S2_PROGRAM_AREA_MISMATCH",
            "Programme space allocations do not reconcile to target GFA",
            {"target_gfa_m2": target_gfa, "allocated_area_m2": round(allocated_area, 3), "residual_m2": round(residual, 3)},
        )

    adjacencies = program.get("adjacencies", [])
    if not isinstance(adjacencies, list):
        raise S2DesignInputError("S2_PROGRAM_INVALID", "Programme adjacencies must be a list")
    normalized_adjacencies = []
    for index, edge in enumerate(adjacencies):
        if not isinstance(edge, dict) or edge.get("from") not in space_ids or edge.get("to") not in space_ids:
            raise S2DesignInputError(
                "S2_PROGRAM_INVALID",
                "Every adjacency must reference two spaces in the current programme",
                {"index": index},
            )
        relationship = edge.get("relationship")
        if not isinstance(relationship, str) or not relationship.strip():
            raise S2DesignInputError("S2_PROGRAM_INVALID", "Every adjacency requires an explicit relationship type", {"index": index})
        normalized_adjacencies.append({
            "from": edge["from"],
            "to": edge["to"],
            "relationship": relationship,
            "required": bool(edge.get("required", False)),
        })

    buildable_area = _finite_number(envelope.get("buildable_area_m2"), field="envelope.buildable_area_m2")
    if buildable_area is None or buildable_area <= 0:
        raise S2DesignInputError("S2_ENVELOPE_INVALID", "The buildable envelope must have positive area")
    max_gfa = _finite_number(envelope.get("max_gfa_m2"), field="envelope.max_gfa_m2", allow_none=True)
    max_height = _finite_number(envelope.get("max_height_m"), field="envelope.max_height_m", allow_none=True)
    if max_gfa is not None and max_gfa <= 0:
        raise S2DesignInputError("S2_ENVELOPE_INVALID", "Maximum GFA must be positive when supplied")
    if max_height is not None and max_height <= 0:
        raise S2DesignInputError("S2_ENVELOPE_INVALID", "Maximum height must be positive when supplied")
    if max_gfa is not None and target_gfa > max_gfa + 1e-6:
        raise S2DesignInputError(
            "PROGRAM_EXCEEDS_ENVELOPE",
            "The programme target GFA exceeds the current planning envelope; revise the programme or verified planning inputs",
            {"program_target_gfa_m2": target_gfa, "envelope_max_gfa_m2": max_gfa},
        )

    floor_count = program.get("floor_count")
    if floor_count is not None and (
        isinstance(floor_count, bool) or not isinstance(floor_count, int) or floor_count < 1
    ):
        raise S2DesignInputError("S2_PROGRAM_INVALID", "Programme floor count must be a positive integer when supplied")

    orientation = (envelope.get("site_orientation") or {}).get("long_axis_degrees_from_north")
    orientation = _finite_number(orientation, field="envelope.site_orientation.long_axis_degrees_from_north", allow_none=True)
    environmental = envelope.get("environmental_context") or {}
    environmental_unknowns = environmental.get("unknowns", [])
    if not isinstance(environmental_unknowns, list):
        environmental_unknowns = []

    return {
        "target_gfa_m2": target_gfa,
        "floor_count": floor_count,
        "program_use": program.get("use"),
        "program_spaces": normalized_spaces,
        "program_adjacencies": normalized_adjacencies,
        "program_assumptions": program.get("assumptions", []) if isinstance(program.get("assumptions", []), list) else [],
        "program_unknowns": program.get("unknowns", []) if isinstance(program.get("unknowns", []), list) else [],
        "buildable_area_m2": buildable_area,
        "max_gfa_m2": max_gfa,
        "max_height_m": max_height,
        "setback_m": _finite_number(envelope.get("setback_m"), field="envelope.setback_m", allow_none=True),
        "orientation_degrees": orientation,
        "environmental_unknowns": environmental_unknowns,
        "site_orientation": envelope.get("site_orientation"),
    }


def apply_s2_design_inputs(candidate: DesignCandidate, inputs: dict[str, Any]) -> DesignCandidate:
    metrics = dict(candidate.metrics)
    parameters = dict(candidate.parameters)
    actual_gfa = _finite_number(metrics.get("gross_floor_area_m2"), field="candidate.gross_floor_area_m2")
    footprint = _finite_number(metrics.get("building_footprint_m2"), field="candidate.building_footprint_m2")
    height = _finite_number(metrics.get("building_height_m"), field="candidate.building_height_m")
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(parameter: str, actual: float, limit: float | None, failure_code: str, unit: str) -> None:
        if limit is None:
            checks.append({"parameter": parameter, "status": "UNKNOWN", "actual": actual, "limit": None, "unit": unit})
            return
        passed = actual <= limit + 1e-6
        checks.append({"parameter": parameter, "status": "PASS" if passed else "FAIL", "actual": actual, "limit": limit, "unit": unit})
        if not passed:
            failures.append(failure_code)

    check("envelope_max_gfa", actual_gfa, inputs["max_gfa_m2"], "MAX_GFA_EXCEEDED", "m2")
    check("envelope_buildable_area", footprint, inputs["buildable_area_m2"], "BUILDABLE_AREA_EXCEEDED", "m2")
    check("envelope_max_height", height, inputs["max_height_m"], "MAX_HEIGHT_EXCEEDED", "m")

    parameters.update({
        "program_use": inputs["program_use"],
        "program_target_gfa_m2": inputs["target_gfa_m2"],
        "program_space_schedule": inputs["program_spaces"],
        "program_adjacencies": inputs["program_adjacencies"],
        "setback_m": inputs["setback_m"] if inputs["setback_m"] is not None else parameters.get("setback_m", 0.0),
        "orientation_degrees": inputs["orientation_degrees"] if inputs["orientation_degrees"] is not None else parameters.get("orientation_degrees"),
    })
    metrics.update({
        "program_target_gfa_m2": inputs["target_gfa_m2"],
        "program_area_deviation_m2": round(actual_gfa - inputs["target_gfa_m2"], 6),
        "envelope_buildable_area_m2": inputs["buildable_area_m2"],
        "envelope_max_gfa_m2": inputs["max_gfa_m2"],
        "envelope_max_height_m": inputs["max_height_m"],
        "program_space_count": len(inputs["program_spaces"]),
        "program_adjacency_count": len(inputs["program_adjacencies"]),
    })
    constraint_results = [
        *candidate.constraint_results,
        *checks,
        {
            "parameter": "program_schedule",
            "status": "PASS",
            "space_count": len(inputs["program_spaces"]),
            "adjacency_count": len(inputs["program_adjacencies"]),
            "note": "The programme schedule and adjacency graph are bound to this massing alternative; room-level floor-plan geometry is not generated in this phase.",
        },
    ]
    assumptions = [*candidate.assumptions, *inputs["program_assumptions"]]
    unknowns = set(candidate.unknowns)
    unknowns.update(inputs["program_unknowns"])
    unknowns.update(inputs["environmental_unknowns"])
    unknowns.add("exact_buildable_polygon_placement")
    reasoning = {
        **candidate.reasoning,
        "program_use": inputs["program_use"],
        "program_target_gfa_m2": inputs["target_gfa_m2"],
        "program_space_count": len(inputs["program_spaces"]),
        "program_adjacency_count": len(inputs["program_adjacencies"]),
        "envelope_orientation_degrees": inputs["orientation_degrees"],
        "envelope_validation": checks,
        "human_review_required": True,
    }
    return candidate.model_copy(update={
        "parameters": parameters,
        "metrics": metrics,
        "constraint_results": constraint_results,
        "assumptions": assumptions,
        "unknowns": sorted(unknowns),
        "reasoning": reasoning,
        "valid": candidate.valid and not failures,
        "invalid_reasons": [*candidate.invalid_reasons, *failures],
    })
