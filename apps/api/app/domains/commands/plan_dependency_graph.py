from __future__ import annotations

from .dependency_graph import DependencyEdge, DependencyGraph, graph_from_edges
from .plan import CommandPlan


def dependency_graph_for_plan(plan: CommandPlan) -> DependencyGraph:
    """Compile immutable command-plan dependencies into the canonical graph projection."""
    plan.validate()
    edges = tuple(
        DependencyEdge(source=dependency, target=node.node_id, relation="command_dependency")
        for node in plan.nodes
        for dependency in node.depends_on
    )
    return graph_from_edges((node.node_id for node in plan.nodes), edges)
