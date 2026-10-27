"""Translate canonical change impact into an ordered regeneration plan."""

from __future__ import annotations

from dataclasses import dataclass

from .change_impact import ChangeImpact


@dataclass(frozen=True)
class RegenerationTask:
    task_id: str
    artifact_type: str
    source_revision_hash: str
    affected_element_ids: tuple[str, ...]
    depends_on: tuple[str, ...]


@dataclass(frozen=True)
class RegenerationPlan:
    source_revision_hash: str
    tasks: tuple[RegenerationTask, ...]


_ORDER = ("geometry", "quantities", "cost", "engineering", "regulatory")


def build_regeneration_plan(impact: ChangeImpact) -> RegenerationPlan:
    """Build stable task IDs and dependency edges for downstream workers."""
    selected = [artifact for artifact in _ORDER if artifact in impact.invalidated_artifacts]
    tasks: list[RegenerationTask] = []
    for index, artifact in enumerate(selected):
        dependencies = tuple(task.task_id for task in tasks)
        task_id = f"regen:{impact.current_hash[:16]}:{index:02d}:{artifact}"
        tasks.append(
            RegenerationTask(
                task_id=task_id,
                artifact_type=artifact,
                source_revision_hash=impact.current_hash,
                affected_element_ids=impact.affected_elements,
                depends_on=dependencies,
            )
        )
    return RegenerationPlan(source_revision_hash=impact.current_hash, tasks=tuple(tasks))


__all__ = ["RegenerationPlan", "RegenerationTask", "build_regeneration_plan"]
