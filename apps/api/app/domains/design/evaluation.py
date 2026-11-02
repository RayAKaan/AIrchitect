from __future__ import annotations

import math
from typing import Any


CRITERIA = (
    "building_footprint_m2",
    "building_height_m",
    "open_site_area_m2",
    "gross_floor_area_fidelity",
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return float(value)


def _objectives(alternative: dict[str, Any]) -> dict[str, tuple[float, bool]]:
    metrics = alternative.get("metrics") or {}
    reasoning = alternative.get("reasoning") or {}
    objectives: dict[str, tuple[float, bool]] = {}
    for key in ("building_footprint_m2", "building_height_m", "open_site_area_m2"):
        value = _number(metrics.get(key))
        if value is not None:
            objectives[key] = (value, key == "open_site_area_m2")
    target = _number(metrics.get("program_target_gfa_m2"))
    if target is None:
        target = _number(reasoning.get("program_target_gfa_m2"))
    if target is None:
        target = _number(reasoning.get("target_gfa_m2"))
    actual = _number(metrics.get("gross_floor_area_m2"))
    if target is not None and target > 0 and actual is not None:
        objectives["gross_floor_area_fidelity"] = (abs(actual - target) / target, False)
    return objectives


def _dominates(left: dict[str, tuple[float, bool]], right: dict[str, tuple[float, bool]]) -> bool:
    shared = sorted(set(left) & set(right))
    if not shared:
        return False
    no_worse = True
    strictly_better = False
    for key in shared:
        left_value, maximize = left[key]
        right_value, _ = right[key]
        if maximize:
            if left_value < right_value - 1e-6:
                no_worse = False
            if left_value > right_value + 1e-6:
                strictly_better = True
        else:
            if left_value > right_value + 1e-6:
                no_worse = False
            if left_value < right_value - 1e-6:
                strictly_better = True
    return no_worse and strictly_better


def evaluate_alternatives(alternatives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add transparent constraint summaries and Pareto comparisons without inventing one overall score."""
    current = [
        alternative
        for alternative in alternatives
        if alternative.get("status") in {"VALID", "SELECTED"}
    ]
    objectives = {alternative["id"]: _objectives(alternative) for alternative in current}
    output = []
    for alternative in alternatives:
        checks = alternative.get("constraint_results") or alternative.get("constraints") or []
        statuses = [
            str(check.get("status", "UNKNOWN")).upper()
            for check in checks
            if isinstance(check, dict)
        ]
        summary = {
            "pass": sum(status == "PASS" for status in statuses),
            "fail": sum(status == "FAIL" for status in statuses),
            "unknown": sum(status not in {"PASS", "FAIL"} for status in statuses),
        }
        is_current = alternative.get("status") in {"VALID", "SELECTED"}
        dominated_by = []
        if is_current:
            own = objectives.get(alternative["id"], {})
            dominated_by = [
                other["id"]
                for other in current
                if other["id"] != alternative["id"]
                and _dominates(objectives.get(other["id"], {}), own)
            ]
        evaluation = {
            "comparable": is_current,
            "constraint_summary": summary,
            "pareto_status": (
                "NOT_COMPARABLE" if not is_current
                else "DOMINATED" if dominated_by
                else "PARETO_FRONTIER"
            ),
            "dominated_by": dominated_by,
            "objectives": objectives.get(alternative.get("id"), {}),
            "criteria": list(CRITERIA),
            "method": "transparent_multi_criteria_pareto_v1",
            "note": "No weighted overall score is used; criteria and trade-offs remain visible for human judgement.",
        }
        output.append({**alternative, "evaluation": evaluation})
    return output
