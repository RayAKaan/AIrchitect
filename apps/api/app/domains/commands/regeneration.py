from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .dependency_graph import DependencyGraph
from .impact import impact_for
from .plan import CommandPlan
from .plan_dependency_graph import dependency_graph_for_plan
from .schemas import CommandEnvelope


@dataclass(frozen=True)
class RegenerationPlan:
    command_id: str
    source_revision_hash: str
    groups: tuple[str, ...]
    requires_recomputation: bool


@dataclass(frozen=True)
class RegenerationBatchPlan:
    source_revision_hash: str
    command_order: tuple[str, ...]
    invalidated_groups: tuple[str, ...]
    requires_recomputation: bool
    dependency_graph: DependencyGraph


def build_regeneration_plan(command: CommandEnvelope) -> RegenerationPlan:
    groups = tuple(impact_for(command))
    return RegenerationPlan(
        command_id=command.command_id,
        source_revision_hash=command.base_revision_hash,
        groups=groups,
        requires_recomputation=bool(groups),
    )


def build_regeneration_batch_plan(plan: CommandPlan, commands: Sequence[CommandEnvelope]) -> RegenerationBatchPlan:
    """Project a validated command plan into deterministic regeneration invalidation."""
    plan.validate()
    graph = dependency_graph_for_plan(plan)
    by_id = {command.command_id: command for command in commands}
    plan_command_ids = {node.command_id for node in plan.nodes}
    if set(by_id) != plan_command_ids:
        raise ValueError("plan and command set do not match")
    if any(command.project_id != plan.project_id or command.version_id != plan.version_id for command in commands):
        raise ValueError("plan and command context do not match")
    if any(command.base_revision_hash != plan.base_revision_hash for command in commands):
        raise ValueError("plan and command revision do not match")

    node_order = graph.topological_order()
    command_by_node = {node.node_id: by_id[node.command_id] for node in plan.nodes}
    command_order = tuple(command_by_node[node_id].command_id for node_id in node_order)
    invalidated_groups = tuple(sorted({group for command in commands for group in impact_for(command)}))
    return RegenerationBatchPlan(
        source_revision_hash=plan.base_revision_hash,
        command_order=command_order,
        invalidated_groups=invalidated_groups,
        requires_recomputation=bool(invalidated_groups),
        dependency_graph=graph,
    )
