from __future__ import annotations

from dataclasses import dataclass

from .schemas import ArchitecturalModel


@dataclass(frozen=True)
class ModelConstraintViolation:
    code: str
    message: str
    element_id: str | None = None


def validate_baseline_constraints(model: ArchitecturalModel) -> tuple[ModelConstraintViolation, ...]:
    """Run structural invariants that are local to the canonical model.

    This intentionally does not perform code compliance or engineering approval;
    those concerns remain separate deterministic domains.
    """
    violations: list[ModelConstraintViolation] = []
    level_heights = {level.id: level.height_m for level in model.levels}
    for opening in (*model.doors, *model.windows):
        wall = next(wall for wall in model.walls if wall.id == opening.host_wall_id)
        if opening.offset_m + opening.width_m > _wall_length(wall):
            violations.append(
                ModelConstraintViolation(
                    code="opening_outside_wall",
                    message=f"Opening {opening.id} extends beyond host wall {wall.id}.",
                    element_id=opening.id,
                )
            )
        if opening.sill_height_m + opening.height_m > level_heights[opening.level_id]:
            violations.append(
                ModelConstraintViolation(
                    code="opening_above_level",
                    message=f"Opening {opening.id} exceeds its level height.",
                    element_id=opening.id,
                )
            )
    return tuple(violations)


def _wall_length(wall) -> float:
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    return (dx * dx + dy * dy) ** 0.5
