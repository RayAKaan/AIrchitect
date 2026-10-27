from __future__ import annotations

from dataclasses import dataclass

from .schemas import ArchitecturalModel


@dataclass(frozen=True)
class ModelDependencyGraph:
    dependencies: dict[str, tuple[str, ...]]

    def direct_dependencies(self, element_id: str) -> tuple[str, ...]:
        return self.dependencies.get(element_id, ())

    def affected_by(self, changed_ids: set[str]) -> tuple[str, ...]:
        """Return deterministic reverse-dependency closure for selective regeneration."""
        affected = set(changed_ids)
        changed = True
        while changed:
            changed = False
            for element_id, dependencies in self.dependencies.items():
                if element_id not in affected and any(dependency in affected for dependency in dependencies):
                    affected.add(element_id)
                    changed = True
        return tuple(sorted(affected))


def build_model_dependency_graph(model: ArchitecturalModel) -> ModelDependencyGraph:
    dependencies: dict[str, tuple[str, ...]] = {model.site.id: ()}

    for building in model.buildings:
        dependencies[building.id] = (building.site_id,)
    for level in model.levels:
        dependencies[level.id] = (level.building_id,)
    for space in model.spaces:
        dependencies[space.id] = (space.level_id,)
    for wall in model.walls:
        dependencies[wall.id] = _sorted_unique((wall.level_id, *wall.space_ids))
    for opening in (*model.doors, *model.windows):
        dependencies[opening.id] = _sorted_unique((opening.level_id, opening.host_wall_id))
    for slab in model.slabs:
        dependencies[slab.id] = _sorted_unique((slab.level_id,)) if slab.level_id else ()
    for stair in model.stairs:
        dependencies[stair.id] = _sorted_unique((stair.level_id, stair.lower_level_id, stair.upper_level_id))

    return ModelDependencyGraph(dependencies=dependencies)


def _sorted_unique(values: tuple[str | None, ...]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value is not None}))
