from __future__ import annotations

from dataclasses import dataclass

from .impact import impact_for
from .schemas import CommandEnvelope


@dataclass(frozen=True)
class RegenerationPlan:
    command_id: str
    source_revision_hash: str
    groups: tuple[str, ...]
    requires_recomputation: bool


def build_regeneration_plan(command: CommandEnvelope) -> RegenerationPlan:
    groups = tuple(impact_for(command))
    return RegenerationPlan(
        command_id=command.command_id,
        source_revision_hash=command.base_revision_hash,
        groups=groups,
        requires_recomputation=bool(groups),
    )
