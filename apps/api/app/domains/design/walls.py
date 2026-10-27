from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from app.domains.model import ArchitecturalModel, Wall


Edge = tuple[tuple[float, float, float], tuple[float, float, float]]


def derive_walls_from_spaces(model: ArchitecturalModel, *, thickness_m: float = 0.2) -> tuple[Wall, ...]:
    """Create deterministic wall centerlines from space boundaries.

    Shared space edges become one wall with both space IDs; non-manifold edges
    are rejected instead of creating ambiguous topology.
    """
    if thickness_m <= 0:
        raise ValueError("wall thickness must be positive")
    if model.walls:
        raise ValueError("cannot derive walls into a model that already contains walls")

    edges: dict[Edge, list[tuple[str, str]]] = defaultdict(list)
    for space in model.spaces:
        points = tuple((point.x, point.y, point.z) for point in space.boundary)
        for start, end in zip(points, (*points[1:], points[0])):
            if start == end:
                raise ValueError(f"space {space.id} contains a zero-length boundary edge")
            edge = _canonical_edge(start, end)
            edges[edge].append((space.level_id, space.id))

    walls: list[Wall] = []
    for edge, owners in sorted(edges.items()):
        if len(owners) > 2:
            raise ValueError(f"boundary edge has more than two owning spaces: {edge}")
        level_ids = {owner[0] for owner in owners}
        if len(level_ids) != 1:
            raise ValueError("a wall edge cannot connect spaces on different levels")
        level_id = next(iter(level_ids))
        start, end = edge
        wall_id = _wall_id(model.project_id, level_id, edge)
        walls.append(
            Wall(
                id=wall_id,
                name="Generated Wall",
                level_id=level_id,
                start=_point(start),
                end=_point(end),
                thickness_m=thickness_m,
                height_m=_level_height(model, level_id),
                space_ids=tuple(sorted(owner[1] for owner in owners)),
            )
        )
    return tuple(walls)


def with_generated_walls(model: ArchitecturalModel, *, thickness_m: float = 0.2) -> ArchitecturalModel:
    walls = derive_walls_from_spaces(model, thickness_m=thickness_m)
    payload = model.model_dump(mode="json")
    payload["walls"] = walls
    return ArchitecturalModel.model_validate(payload)


def _canonical_edge(start: tuple[float, float, float], end: tuple[float, float, float]) -> Edge:
    return (start, end) if start <= end else (end, start)


def _point(value: tuple[float, float, float]):
    from app.domains.model import Point3D

    return Point3D(x=value[0], y=value[1], z=value[2])


def _level_height(model: ArchitecturalModel, level_id: str) -> float:
    for level in model.levels:
        if level.id == level_id:
            return level.height_m
    raise ValueError(f"unknown level: {level_id}")


def _wall_id(project_id: str, level_id: str, edge: Edge) -> str:
    payload = json.dumps([project_id, level_id, edge], separators=(",", ":"), sort_keys=True).encode("utf-8")
    return f"wall-{hashlib.sha256(payload).hexdigest()[:16]}"
