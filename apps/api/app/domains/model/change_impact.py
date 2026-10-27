"""Deterministic downstream impact planning for canonical model revisions."""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.model import ArchitecturalModel, canonical_model_payload, model_hash
from app.domains.model.dependencies import build_dependency_graph


@dataclass(frozen=True)
class ModelChange:
    element_id: str
    change_type: str


@dataclass(frozen=True)
class ChangeImpact:
    previous_hash: str
    current_hash: str
    changed_elements: tuple[ModelChange, ...]
    affected_elements: tuple[str, ...]
    invalidated_artifacts: tuple[str, ...]


def plan_change_impact(previous: ArchitecturalModel, current: ArchitecturalModel) -> ChangeImpact:
    """Compare canonical state and expand changed IDs through dependency closure."""
    if previous.project_id != current.project_id:
        raise ValueError("cannot compare models from different projects")
    old = _element_payloads(previous)
    new = _element_payloads(current)
    changes: list[ModelChange] = []
    for element_id in sorted(set(old) | set(new)):
        if element_id not in old:
            changes.append(ModelChange(element_id, "created"))
        elif element_id not in new:
            changes.append(ModelChange(element_id, "deleted"))
        elif old[element_id] != new[element_id]:
            changes.append(ModelChange(element_id, "updated"))

    graph = build_dependency_graph(current)
    affected = set(item.element_id for item in changes)
    for item in tuple(affected):
        affected.update(graph.affected_by(item))
    artifact_map = {
        "geometry": bool(changes),
        "quantities": bool(changes),
        "cost": bool(changes),
        "engineering": bool(changes),
        "regulatory": bool(changes),
    }
    invalidated = tuple(name for name, enabled in artifact_map.items() if enabled)
    return ChangeImpact(
        previous_hash=model_hash(previous),
        current_hash=model_hash(current),
        changed_elements=tuple(changes),
        affected_elements=tuple(sorted(affected)),
        invalidated_artifacts=invalidated,
    )


def _element_payloads(model: ArchitecturalModel) -> dict[str, object]:
    payload = canonical_model_payload(model)
    result: dict[str, object] = {}
    for key in ("buildings", "levels", "spaces", "walls", "doors", "windows", "slabs", "stairs"):
        for item in payload.get(key, []):
            result[str(item["id"])] = item
    result[model.site.id] = payload["site"]
    return result


__all__ = ["ChangeImpact", "ModelChange", "plan_change_impact"]
