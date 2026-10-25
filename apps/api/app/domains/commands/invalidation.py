from __future__ import annotations

from dataclasses import dataclass

from .regeneration import RegenerationPlan
from .regeneration_engine import execution_steps


@dataclass(frozen=True)
class Invalidation:
    group: str
    reason: str
    source_revision_hash: str


def invalidations_for(plan: RegenerationPlan) -> tuple[Invalidation, ...]:
    """Translate command regeneration impact into explicit stale projections."""
    return tuple(
        Invalidation(
            group=step.group,
            reason=f"command:{plan.command_id}",
            source_revision_hash=plan.source_revision_hash,
        )
        for step in execution_steps(plan)
    )
