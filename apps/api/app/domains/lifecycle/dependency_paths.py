from __future__ import annotations

from collections.abc import Mapping


def shortest_dependency_path(graph: Mapping[str, set[str]], start: str, target: str) -> tuple[str, ...]:
    if start == target:
        return (start,)
    queue: list[tuple[str, tuple[str, ...]]] = [(start, (start,))]
    visited = {start}
    while queue:
        node, path = queue.pop(0)
        for dependency in sorted(graph.get(node, ())):
            if dependency in visited:
                continue
            next_path = (*path, dependency)
            if dependency == target:
                return next_path
            visited.add(dependency)
            queue.append((dependency, next_path))
    return ()
