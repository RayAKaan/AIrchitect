from __future__ import annotations

from dataclasses import dataclass
from .plan import CommandPlan


@dataclass(frozen=True)
class PlanContract:
    executable: bool
    reason: str | None = None


def contract_for(plan: CommandPlan) -> PlanContract:
    try:
        plan.validate()
    except ValueError as exc:
        return PlanContract(False, str(exc))
    if not plan.nodes:
        return PlanContract(False, "command plan must not be empty")
    return PlanContract(True)
