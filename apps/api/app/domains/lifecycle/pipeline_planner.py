from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelinePlan:
    """Topologically ordered stages for one deterministic pipeline execution."""

    stages: tuple[str, ...]


def plan_pipeline(stages: set[str], dependencies: dict[str, set[str]]) -> PipelinePlan:
    """Return a stable topological order and reject unknown or cyclic dependencies."""
    if any(not stage.strip() for stage in stages):
        raise ValueError("stage names must not be empty")
    unknown = set(dependencies) - stages
    unknown_dependencies = {
        dependency for values in dependencies.values() for dependency in values if dependency not in stages
    }
    if unknown or unknown_dependencies:
        raise ValueError("pipeline dependencies reference unknown stages")

    remaining = {stage: set(dependencies.get(stage, set())) for stage in stages}
    ordered: list[str] = []
    while remaining:
        ready = sorted(stage for stage, deps in remaining.items() if not deps)
        if not ready:
            raise ValueError("pipeline dependency graph contains a cycle")
        ordered.extend(ready)
        for stage in ready:
            remaining.pop(stage)
        for deps in remaining.values():
            deps.difference_update(ready)
    return PipelinePlan(tuple(ordered))
