from __future__ import annotations

from dataclasses import dataclass
from .dependency_graph import DependencyGraph


@dataclass(frozen=True)
class RegenerationStep:
    node_id: str
    reason: str


def plan_regeneration(graph: DependencyGraph, changed_nodes: tuple[str, ...]) -> tuple[RegenerationStep, ...]:
    graph.validate()
    changed = set(changed_nodes)
    unknown = changed - set(graph.nodes)
    if unknown:
        raise ValueError(f"changed nodes are unknown: {sorted(unknown)}")
    affected = set(changed)
    frontier = list(changed)
    while frontier:
        current = frontier.pop(0)
        for dependent in graph.dependents_of(current):
            if dependent not in affected:
                affected.add(dependent)
                frontier.append(dependent)
    ordered = _stable_topological_subset(graph, affected)
    return tuple(RegenerationStep(node_id, "changed" if node_id in changed else "dependent") for node_id in ordered)


def _stable_topological_subset(graph: DependencyGraph, subset: set[str]) -> tuple[str, ...]:
    incoming = {node: {dep for dep in graph.dependencies_of(node) if dep in subset} for node in subset}
    ordered: list[str] = []
    while incoming:
        ready = sorted(node for node, deps in incoming.items() if not deps)
        if not ready:
            raise ValueError("dependency graph contains a cycle")
        ordered.extend(ready)
        for node in ready:
            incoming.pop(node)
        for deps in incoming.values():
            deps.difference_update(ready)
    return tuple(ordered)
