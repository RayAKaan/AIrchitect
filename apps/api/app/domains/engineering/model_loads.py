"""Preliminary structural load derivation from the canonical architectural model.

This is a deterministic screening calculation, not a stamped structural design.
It intentionally reports assumptions and refuses to present results as code
compliance or final member design.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.model import ArchitecturalModel


@dataclass(frozen=True)
class LoadAssumptions:
    dead_load_kpa: float = 1.5
    live_load_kpa: float = 2.0
    roof_live_load_kpa: float = 0.75
    load_factor_dead: float = 1.2
    load_factor_live: float = 1.6


@dataclass(frozen=True)
class SpaceLoad:
    space_id: str
    level_id: str
    area_m2: float
    dead_load_kn: float
    live_load_kn: float
    factored_load_kn: float


@dataclass(frozen=True)
class LevelLoad:
    level_id: str
    elevation_m: float
    tributary_area_m2: float
    dead_load_kn: float
    live_load_kn: float
    factored_load_kn: float


@dataclass(frozen=True)
class PreliminaryLoadEnvelope:
    model_hash: str
    assumptions: LoadAssumptions
    spaces: tuple[SpaceLoad, ...]
    levels: tuple[LevelLoad, ...]
    total_factored_load_kn: float
    is_screening_only: bool = True


def derive_preliminary_loads(
    model: ArchitecturalModel,
    *,
    assumptions: LoadAssumptions = LoadAssumptions(),
) -> PreliminaryLoadEnvelope:
    """Calculate transparent area-based vertical gravity loads."""
    if assumptions.dead_load_kpa < 0 or assumptions.live_load_kpa < 0:
        raise ValueError("load intensities must be non-negative")
    spaces: list[SpaceLoad] = []
    by_level: dict[str, list[SpaceLoad]] = {}
    for space in sorted(model.spaces, key=lambda item: item.id):
        area = _polygon_area(space.boundary)
        dead = area * assumptions.dead_load_kpa
        live = area * assumptions.live_load_kpa
        item = SpaceLoad(
            space_id=space.id,
            level_id=space.level_id,
            area_m2=area,
            dead_load_kn=dead,
            live_load_kn=live,
            factored_load_kn=dead * assumptions.load_factor_dead + live * assumptions.load_factor_live,
        )
        spaces.append(item)
        by_level.setdefault(space.level_id, []).append(item)

    levels_by_id = {level.id: level for level in model.levels}
    levels: list[LevelLoad] = []
    for level_id in sorted(by_level):
        level = levels_by_id[level_id]
        members = by_level[level_id]
        levels.append(
            LevelLoad(
                level_id=level_id,
                elevation_m=level.elevation_m,
                tributary_area_m2=sum(item.area_m2 for item in members),
                dead_load_kn=sum(item.dead_load_kn for item in members),
                live_load_kn=sum(item.live_load_kn for item in members),
                factored_load_kn=sum(item.factored_load_kn for item in members),
            )
        )
    return PreliminaryLoadEnvelope(
        model_hash=_model_hash(model),
        assumptions=assumptions,
        spaces=tuple(spaces),
        levels=tuple(levels),
        total_factored_load_kn=sum(item.factored_load_kn for item in levels),
    )


def _polygon_area(boundary: tuple[object, ...]) -> float:
    points = [(float(point.x), float(point.y)) for point in boundary]
    return abs(sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )) / 2.0


def _model_hash(model: ArchitecturalModel) -> str:
    from app.domains.model import model_hash
    return model_hash(model)


__all__ = ["LevelLoad", "LoadAssumptions", "PreliminaryLoadEnvelope", "SpaceLoad", "derive_preliminary_loads"]
