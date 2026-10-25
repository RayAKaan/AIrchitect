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

    def validate(self) -> None:
        known = set(self.nodes)
        if len(known) != len(self.nodes):
            raise ValueError("dependency graph nodes must be unique")
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError("dependency edge references an unknown node")
            if edge.source == edge.target:
                raise ValueError("dependency graph cannot contain self-edges")


def graph_from_edges(nodes: Iterable[str], edges: Iterable[DependencyEdge]) -> DependencyGraph:
    graph = DependencyGraph(tuple(dict.fromkeys(nodes)), tuple(edges))
    graph.validate()
    return graph
