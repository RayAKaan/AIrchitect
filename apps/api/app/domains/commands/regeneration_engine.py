from __future__ import annotations

from dataclasses import dataclass

from .regeneration import RegenerationPlan

_ORDER = (
    "requirements",
    "program",
    "envelope",
    "concepts",
    "semantic_model",
    "parametric_geometry_intents",
    "drawings",
    "analysis",
)


@dataclass(frozen=True)
class RegenerationStep:
    group: str
    ordinal: int


def execution_steps(plan: RegenerationPlan) -> tuple[RegenerationStep, ...]:
    """Produce a stable topological order for known regeneration groups."""
    rank = {name: index for index, name in enumerate(_ORDER)}
    unknown = sorted(group for group in plan.groups if group not in rank)
    if unknown:
        raise ValueError(f"unknown regeneration groups: {', '.join(unknown)}")
    ordered = sorted(set(plan.groups), key=lambda group: rank[group])
    return tuple(RegenerationStep(group, rank[group]) for group in ordered)
