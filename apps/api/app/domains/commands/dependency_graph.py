from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    relation: str


@dataclass(frozen=True)
class DependencyGraph:
    nodes: tuple[str, ...]
    edges: tuple[DependencyEdge, ...]

    def dependents_of(self, node_id: str) -> tuple[str, ...]:
        return tuple(sorted(edge.target for edge in self.edges if edge.source == node_id))

    def dependencies_of(self, node_id: str) -> tuple[str, ...]:
        return tuple(sorted(edge.source for edge in self.edges if edge.target == node_id))

    def topological_order(self) -> tuple[str, ...]:
        self.validate()
        incoming = {node_id: set(self.dependencies_of(node_id)) for node_id in self.nodes}
        ordered: list[str] = []
        while incoming:
            ready = sorted(node_id for node_id, deps in incoming.items() if not deps)
            if not ready:
                raise ValueError("dependency graph contains a dependency cycle")
            ordered.extend(ready)
            for node_id in ready:
                incoming.pop(node_id)
            for deps in incoming.values():
                deps.difference_update(ready)
        return tuple(ordered)

    def validate(self) -> None:
        known = set(self.nodes)
        if len(known) != len(self.nodes):
            raise ValueError("dependency graph nodes must be unique")
        seen_edges: set[tuple[str, str, str]] = set()
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError("dependency edge references an unknown node")
            if edge.source == edge.target:
                raise ValueError("dependency graph cannot contain self-edges")
            identity = (edge.source, edge.target, edge.relation)
            if identity in seen_edges:
                raise ValueError("dependency graph edges must be unique")
            seen_edges.add(identity)
        if self.edges:
            self._validate_acyclic()

    def _validate_acyclic(self) -> None:
        incoming = {node_id: set(self.dependencies_of(node_id)) for node_id in self.nodes}
        remaining = dict(incoming)
        while remaining:
            ready = [node_id for node_id, deps in remaining.items() if not deps]
            if not ready:
                raise ValueError("dependency graph contains a dependency cycle")
            for node_id in ready:
                remaining.pop(node_id)
            for deps in remaining.values():
                deps.difference_update(ready)


def graph_from_edges(nodes: Iterable[str], edges: Iterable[DependencyEdge]) -> DependencyGraph:
    graph = DependencyGraph(tuple(dict.fromkeys(nodes)), tuple(edges))
    graph.validate()
    return graph
