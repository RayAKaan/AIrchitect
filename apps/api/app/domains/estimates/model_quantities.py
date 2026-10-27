"""Deterministic quantities and transparent conceptual cost projection."""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.geometry.model_derivation import derive_model_meshes
from app.domains.model import ArchitecturalModel


@dataclass(frozen=True)
class QuantityRate:
    wall_area_rate_per_m2: float = 35.0
    floor_area_rate_per_m2: float = 50.0
    slab_volume_rate_per_m3: float = 300.0


@dataclass(frozen=True)
class ModelQuantities:
    model_hash: str
    floor_area_m2: float
    wall_surface_area_m2: float
    slab_volume_m3: float
    conceptual_cost: float
    is_conceptual: bool = True


def derive_model_quantities(
    model: ArchitecturalModel,
    *,
    rates: QuantityRate = QuantityRate(),
) -> ModelQuantities:
    """Derive quantities from canonical geometry, never from user-entered totals."""
    if min(rates.wall_area_rate_per_m2, rates.floor_area_rate_per_m2, rates.slab_volume_rate_per_m3) < 0:
        raise ValueError("quantity rates must be non-negative")
    meshes = derive_model_meshes(model)
    floor_area = sum(_polygon_area(space.boundary) for space in model.spaces)
    wall_area = sum(_mesh_surface_area(mesh.vertices, mesh.faces) for mesh in meshes if mesh.element_type == "wall")
    slab_volume = sum(_polygon_area(slab.boundary) * slab.thickness_m for slab in model.slabs)
    cost = (
        floor_area * rates.floor_area_rate_per_m2
        + wall_area * rates.wall_area_rate_per_m2
        + slab_volume * rates.slab_volume_rate_per_m3
    )
    from app.domains.model import model_hash
    return ModelQuantities(
        model_hash=model_hash(model),
        floor_area_m2=floor_area,
        wall_surface_area_m2=wall_area,
        slab_volume_m3=slab_volume,
        conceptual_cost=cost,
    )


def _polygon_area(boundary: tuple[object, ...]) -> float:
    points = [(float(point.x), float(point.y)) for point in boundary]
    return abs(sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points)))) / 2


def _mesh_surface_area(vertices: tuple[tuple[float, float, float], ...], faces: tuple[tuple[int, ...], ...]) -> float:
    total = 0.0
    for face in faces:
        if len(face) < 3:
            continue
        origin = vertices[face[0]]
        for i in range(1, len(face) - 1):
            a, b = vertices[face[i]], vertices[face[i + 1]]
            ux, uy, uz = (a[j] - origin[j] for j in range(3))
            vx, vy, vz = (b[j] - origin[j] for j in range(3))
            total += 0.5 * ((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2) ** 0.5
    return total


__all__ = ["ModelQuantities", "QuantityRate", "derive_model_quantities"]
