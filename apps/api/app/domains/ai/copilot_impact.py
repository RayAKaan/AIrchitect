from __future__ import annotations

from dataclasses import dataclass

from app.domains.commands.artifact_invalidation import GROUP_TO_ARTIFACT_TYPE


_IMPACT_DESCRIPTIONS: dict[str, str] = {
    "planning_envelope": "Planning envelope and feasibility assumptions may need regeneration.",
    "design_alternatives": "Design alternatives derived from the changed state may become stale.",
    "parametric_geometry_intents": "Parametric geometry intent and downstream geometry artifacts may become stale.",
    "program": "Program and space allocation artifacts may need regeneration.",
    "quantities": "Quantity takeoffs derived from the changed geometry may need regeneration.",
    "cost": "Cost artifacts derived from quantities may need regeneration.",
    "structural_review": "Structural review artifacts depending on the changed design may need regeneration.",
    "validation": "Validation artifacts must be recomputed against the new canonical revision.",
}


@dataclass(frozen=True)
class ImpactExplanation:
    group: str
    artifact_type: str
    description: str
    regeneration_required: bool = True


def explain_impact_groups(groups: tuple[str, ...] | list[str]) -> tuple[ImpactExplanation, ...]:
    """Return deterministic, user-facing impact explanations for validated groups."""
    normalized = tuple(dict.fromkeys(groups))
    unknown = sorted(group for group in normalized if group not in GROUP_TO_ARTIFACT_TYPE)
    if unknown:
        raise ValueError(f"UNKNOWN_IMPACT_GROUP:{','.join(unknown)}")
    return tuple(
        ImpactExplanation(
            group=group,
            artifact_type=GROUP_TO_ARTIFACT_TYPE[group],
            description=_IMPACT_DESCRIPTIONS[group],
        )
        for group in normalized
    )
