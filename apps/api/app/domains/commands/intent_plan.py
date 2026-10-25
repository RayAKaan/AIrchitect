from __future__ import annotations

from collections.abc import Sequence
from .plan import CommandPlan
from .plan_builder import build_sequential_plan
from .schemas import CommandEnvelope


def build_intent_plan(plan_id: str, commands: Sequence[CommandEnvelope]) -> CommandPlan:
    """Compose already-validated command proposals without adding semantics."""
    return build_sequential_plan(plan_id, commands)
