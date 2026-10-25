from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PlanNode:
    node_id: str
    command_id: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommandPlan:
    plan_id: str
    project_id: str
    version_id: str
    base_revision_hash: str
    nodes: tuple[PlanNode, ...]

    def validate(self) -> None:
        ids = [node.node_id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("plan node ids must be unique")
        known = set(ids)
        for node in self.nodes:
            if node.node_id in node.depends_on:
                raise ValueError("plan node cannot depend on itself")
            missing = set(node.depends_on) - known
            if missing:
                raise ValueError(f"plan contains unknown dependencies: {sorted(missing)}")
        _topological_order(self.nodes)

    def execution_order(self) -> tuple[str, ...]:
        self.validate()
        return _topological_order(self.nodes)


def _topological_order(nodes: Iterable[PlanNode]) -> tuple[str, ...]:
    by_id = {node.node_id: node for node in nodes}
    incoming = {node_id: set(node.depends_on) for node_id, node in by_id.items()}
    ordered: list[str] = []
    while incoming:
        ready = sorted(node_id for node_id, deps in incoming.items() if not deps)
        if not ready:
            raise ValueError("command plan contains a dependency cycle")
        ordered.extend(ready)
        for node_id in ready:
            incoming.pop(node_id)
        for deps in incoming.values():
            deps.difference_update(ready)
    return tuple(ordered)
