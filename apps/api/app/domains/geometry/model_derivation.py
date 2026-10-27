from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from shapely.geometry import Polygon
from shapely.ops import triangulate

from app.domains.model import ArchitecturalModel, Slab, Space, Wall, model_hash


@dataclass(frozen=True)
class DerivedMesh:
    element_id: str
    element_type: str
    source_model_hash: str
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    geometry_hash: str


def derive_model_meshes(model: ArchitecturalModel) -> tuple[DerivedMesh, ...]:
    """Derive presentation geometry from canonical parametric state only."""
    source_hash = model_hash(model)
    meshes = [*_derive_spaces(model.spaces, source_hash), *_derive_walls(model.walls, source_hash), *_derive_slabs(model.slabs, source_hash)]
    return tuple(sorted(meshes, key=lambda mesh: (mesh.element_type, mesh.element_id)))


def _derive_walls(walls: tuple[Wall, ...], source_hash: str) -> list[DerivedMesh]:
    result: list[DerivedMesh] = []
    for wall in walls:
        dx = wall.end.x - wall.start.x
        dy = wall.end.y - wall.start.y
        length = math.hypot(dx, dy)
        if length <= 0:
            raise ValueError(f"wall {wall.id} has zero length")
        nx = -dy / length * wall.thickness_m / 2
        ny = dx / length * wall.thickness_m / 2
        z0 = wall.start.z
        z1 = z0 + wall.height_m
        vertices = (
            (wall.start.x + nx, wall.start.y + ny, z0),
            (wall.end.x + nx, wall.end.y + ny, z0),
            (wall.end.x - nx, wall.end.y - ny, z0),
            (wall.start.x - nx, wall.start.y - ny, z0),
            (wall.start.x + nx, wall.start.y + ny, z1),
            (wall.end.x + nx, wall.end.y + ny, z1),
            (wall.end.x - nx, wall.end.y - ny, z1),
            (wall.start.x - nx, wall.start.y - ny, z1),
        )
        faces = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
        result.append(_mesh(wall.id, "wall", source_hash, vertices, faces))
    return result


def _derive_spaces(spaces: tuple[Space, ...], source_hash: str) -> list[DerivedMesh]:
    result: list[DerivedMesh] = []
    for space in spaces:
        polygon = _polygon(space.boundary, space.id)
        triangles = sorted(triangulate(polygon), key=lambda triangle: (triangle.centroid.x, triangle.centroid.y, triangle.area))
        vertices: list[tuple[float, float, float]] = []
        faces: list[tuple[int, int, int]] = []
        index: dict[tuple[float, float, float], int] = {}
        for triangle in triangles:
            if not polygon.covers(triangle.representative_point()):
                continue
            coords = list(triangle.exterior.coords)[:-1]
            face: list[int] = []
            for x, y in coords:
                point = (float(x), float(y), space.boundary[0].z)
                if point not in index:
                    index[point] = len(vertices)
                    vertices.append(point)
                face.append(index[point])
            faces.append(tuple(face))
        if not faces:
            raise ValueError(f"space {space.id} has no triangulatable area")
        result.append(_mesh(space.id, "space", source_hash, tuple(vertices), tuple(faces)))
    return result


def _derive_slabs(slabs: tuple[Slab, ...], source_hash: str) -> list[DerivedMesh]:
    result: list[DerivedMesh] = []
    for slab in slabs:
        polygon = _polygon(slab.boundary, slab.id)
        triangles = sorted(triangulate(polygon), key=lambda triangle: (triangle.centroid.x, triangle.centroid.y, triangle.area))
        top_z = slab.boundary[0].z + slab.thickness_m
        vertices: list[tuple[float, float, float]] = []
        faces: list[tuple[int, int, int]] = []
        index: dict[tuple[float, float, float], int] = {}
        for triangle in triangles:
            if not polygon.covers(triangle.representative_point()):
                continue
            coords = list(triangle.exterior.coords)[:-1]
            bottom: list[int] = []
            top: list[int] = []
            for x, y in coords:
                lower = (float(x), float(y), slab.boundary[0].z)
                upper = (float(x), float(y), top_z)
                if lower not in index:
                    index[lower] = len(vertices)
                    vertices.append(lower)
                if upper not in index:
                    index[upper] = len(vertices)
                    vertices.append(upper)
                bottom.append(index[lower])
                top.append(index[upper])
            faces.extend((tuple(reversed(bottom)), tuple(top)))
        if not faces:
            raise ValueError(f"slab {slab.id} has no triangulatable area")
        result.append(_mesh(slab.id, "slab", source_hash, tuple(vertices), tuple(faces)))
    return result


def _polygon(boundary, element_id: str) -> Polygon:
    polygon = Polygon([(point.x, point.y) for point in boundary])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError(f"{element_id} boundary is not a valid positive-area polygon")
    return polygon


def _mesh(element_id: str, element_type: str, source_hash: str, vertices, faces) -> DerivedMesh:
    payload = {"vertices": vertices, "faces": faces}
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return DerivedMesh(
        element_id=element_id,
        element_type=element_type,
        source_model_hash=source_hash,
        vertices=tuple(vertices),
        faces=tuple(faces),
        geometry_hash=hashlib.sha256(encoded).hexdigest(),
    )
