"""Conservative model-level regulatory screening checks.

These checks are jurisdiction-neutral geometry gates. They do not claim code
compliance; jurisdiction-specific rules must provide their own evidence layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.model import ArchitecturalModel


@dataclass(frozen=True)
class RegulatoryRuleSet:
    front_setback_m: float = 0.0
    rear_setback_m: float = 0.0
    side_setback_m: float = 0.0
    max_floors: int | None = None
    max_building_height_m: float | None = None


@dataclass(frozen=True)
class RegulatoryFinding:
    code: str
    status: str
    message: str
    element_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegulatoryScreening:
    model_hash: str
    passed: bool
    findings: tuple[RegulatoryFinding, ...]
    jurisdiction_specific_required: bool = True


def screen_model(model: ArchitecturalModel, rules: RegulatoryRuleSet) -> RegulatoryScreening:
    """Run deterministic, explainable envelope checks against canonical spaces."""
    if min(rules.front_setback_m, rules.rear_setback_m, rules.side_setback_m) < 0:
        raise ValueError("setbacks must be non-negative")
    findings: list[RegulatoryFinding] = []
    min_x = model.site.origin.x + rules.side_setback_m
    max_x = model.site.origin.x + model.site.width_m - rules.side_setback_m
    min_y = model.site.origin.y + rules.front_setback_m
    max_y = model.site.origin.y + model.site.depth_m - rules.rear_setback_m

    for space in sorted(model.spaces, key=lambda item: item.id):
        outside = [
            point for point in space.boundary
            if not (min_x <= point.x <= max_x and min_y <= point.y <= max_y)
        ]
        if outside:
            findings.append(RegulatoryFinding(
                code="SETBACK_ENVELOPE",
                status="FAIL",
                message="space boundary extends outside the configured screening envelope",
                element_ids=(space.id,),
            ))

    level_ids = {level.id for level in model.levels}
    levels = sorted(model.levels, key=lambda item: (item.elevation_m, item.id))
    if rules.max_floors is not None and len(levels) > rules.max_floors:
        findings.append(RegulatoryFinding(
            code="MAX_FLOORS",
            status="FAIL",
            message=f"model has {len(levels)} levels; maximum is {rules.max_floors}",
            element_ids=tuple(level.id for level in levels),
        ))
    if rules.max_building_height_m is not None and levels:
        top = max(level.elevation_m + level.height_m for level in levels)
        if top - model.site.origin.z > rules.max_building_height_m:
            findings.append(RegulatoryFinding(
                code="MAX_HEIGHT",
                status="FAIL",
                message=f"building top elevation {top:g}m exceeds maximum height",
                element_ids=tuple(level.id for level in levels),
            ))

    for stair in model.stairs:
        if stair.lower_level_id not in level_ids or stair.upper_level_id not in level_ids:
            findings.append(RegulatoryFinding(
                code="STAIR_LEVEL_REFERENCE",
                status="FAIL",
                message="stair references an unknown level",
                element_ids=(stair.id,),
            ))
    if not findings:
        findings.append(RegulatoryFinding(
            code="SCREENING_PASS",
            status="PASS",
            message="model satisfies all configured jurisdiction-neutral screening rules",
        ))
    return RegulatoryScreening(
        model_hash=_hash(model),
        passed=not any(item.status == "FAIL" for item in findings),
        findings=tuple(findings),
    )


def _hash(model: ArchitecturalModel) -> str:
    from app.domains.model import model_hash
    return model_hash(model)


__all__ = ["RegulatoryFinding", "RegulatoryRuleSet", "RegulatoryScreening", "screen_model"]
