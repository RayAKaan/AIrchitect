from __future__ import annotations

import math

from .schemas import ArchitecturalModel


def validate_opening_integrity(model: ArchitecturalModel) -> None:
    """Ensure every hosted opening remains physically contained by its wall."""
    walls = {wall.id: wall for wall in model.walls}
    for opening in (*model.doors, *model.windows):
        wall = walls.get(opening.host_wall_id)
        if wall is None:
            raise ValueError(f"opening {opening.id!r} references missing wall {opening.host_wall_id!r}")
        wall_length = math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)
        if opening.offset_m + opening.width_m > wall_length + 1e-9:
            raise ValueError(
                f"opening {opening.id!r} no longer fits host wall {wall.id!r}"
            )
        if opening.height_m + opening.sill_height_m > wall.height_m + 1e-9:
            raise ValueError(
                f"opening {opening.id!r} exceeds host wall {wall.id!r} height"
            )
