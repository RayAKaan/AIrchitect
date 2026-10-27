from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

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
    meshes = [
        *_derive_spaces(model.spaces, source_hash),
        *_derive_walls(model.walls, (*model.doors, *model.windows), source_hash),
        *_derive_slabs(model.slabs, source_hash),
    ]
    return tuple(sorted(meshes, key=lambda mesh: (mesh.element_type, mesh.element_id)))


def _derive_walls(walls: tuple[Wall, ...], openings: tuple[Any, ...], source_hash: str) -> list[DerivedMesh]:
    openings_by_wall: dict[str, list[Any]] = {}
    for opening in openings:
        openings_by_wall.setdefault(opening.host_wall_id, []).append(opening)

    result: list[DerivedMesh] = []
    for wall in walls:
        dx = wall.end.x - wall.start.x
        dy = wall.end.y - wall.start.y
        length = math.hypot(dx, dy)
        if length <= 0:
            raise ValueError(f"wall {wall.id} has zero length")
        nx = -dy / length * wall.thickness_m / 2
        ny = dx / length * wall.thickness_m / 2
        local_openings = sorted(openings_by_wall.get(wall.id, []), key=lambda item: (item.offset_m, item.sill_height_m, item.id))
        _validate_openings(wall, local_openings, length)

        vertices: list[tuple[float, float, float]] = []
        faces: list[tuple[int, ...]] = []
        vertex_index: dict[tuple[float, float, float], int] = {}
        x_breaks = {0.0, length}
        for opening in local_openings:
            x_breaks.update((float(opening.offset_m), float(opening.offset_m + opening.width_m)))

        x_values = sorted(x_breaks)
        for xa, xb in zip(x_values, x_values[1:]):
            if xb - xa <= 1e-9:
                continue
            active = [opening for opening in local_openings if opening.offset_m < xb and opening.offset_m + opening.width_m > xa]
            z_breaks = {0.0, float(wall.height_m)}
            for opening in active:
                z_breaks.update((float(opening.sill_height_m), float(opening.sill_height_m + opening.height_m)))
            z_values = sorted(z_breaks)
            for za, zb in zip(z_values, z_values[1:]):
                if zb - za <= 1e-9:
                    continue
                midpoint_x = (xa + xb) / 2
                midpoint_z = (za + zb) / 2
                if any(
                    opening.offset_m < midpoint_x < opening.offset_m + opening.width_m
                    and opening.sill_height_m < midpoint_z < opening.sill_height_m + opening.height_m
                    for opening in active
                ):
                    continue
                prism_vertices = _wall_prism_vertices(wall, nx, ny, xa, xb, za, zb, length)
                prism_faces = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
                mapped = []
                for point in prism_vertices:
                    if point not in vertex_index:
                        vertex_index[point] = len(vertices)
                        vertices.append(point)
                    mapped.append(vertex_index[point])
                faces.extend(tuple(mapped[index] for index in face) for face in prism_faces)
        if not faces:
            raise ValueError(f"wall {wall.id} has no solid geometry after openings")
        result.append(_mesh(wall.id, "wall", source_hash, tuple(vertices), tuple(faces)))
    return result


def _validate_openings(wall: Wall, openings: list[Any], length: float) -> None:
    for opening in openings:
        if opening.offset_m + opening.width_m > length + 1e-9:
            raise ValueError(f"opening {opening.id} extends beyond wall {wall.id}")
        if opening.sill_height_m + opening.height_m > wall.height_m + 1e-9:
            raise ValueError(f"opening {opening.id} extends above wall {wall.id}")
    for index, left in enumerate(openings):
        for right in openings[index + 1 :]:
            x_overlap = left.offset_m < right.offset_m + right.width_m and right.offset_m < left.offset_m + left.width_m
            z_overlap = left.sill_height_m < right.sill_height_m + right.height_m and right.sill_height_m < left.sill_height_m + left.height_m
            if x_overlap and z_overlap:
                raise ValueError(f"openings {left.id} and {right.id} overlap on wall {wall.id}")


def _wall_prism_vertices(wall: Wall, nx: float, ny: float, xa: float, xb: float, za: float, zb: float, length: float) -> tuple[tuple[float, float, float], ...]:
    dx = (wall.end.x - wall.start.x) / length
    dy = (wall.end.y - wall.start.y) / length

    def point(distance: float, offset_x: float, z: float) -> tuple[float, float, float]:
        center_x = wall.start.x + dx * distance
        center_y = wall.start.y + dy * distance
        return (center_x + offset_x * nx, center_y + offset_x * ny, wall.start.z + z)

    return (
        point(xa, 1, za), point(xb, 1, za), point(xb, -1, za), point(xa, -1, za),
        point(xa, 1, zb), point(xb, 1, zb), point(xb, -1, zb), point(xa, -1, zb),
    )


def _derive_spaces(spaces: tuple[Space, ...], source_hash: str) -> list[DerivedMesh]:
    result: list[DerivedMesh] = []
    for space in spaces:
        polygon = _polygon(space.boundary, space.id)
        triangles = sorted(triangulate(polygon), key=lambda triangle: (triangle.centroid.x, triangle.centroid.y, triangle.area))
        vertices: list[tuple[float, float, float]] = []
        faces: list[tuple[int, int, int]] = []
        index: dict[tuple[float, float, float], int] = {}
        for triangle in triangles:
            if not polygon.covers(triangle):
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
        bottom_z = slab.boundary[0].z
        top_z = bottom_z + slab.thickness_m
        vertices: list[tuple[float, float, float]] = []
        faces: list[tuple[int, ...]] = []
        index: dict[tuple[float, float, float], int] = {}

        def vertex(point: tuple[float, float, float]) -> int:
            if point not in index:
                index[point] = len(vertices)
                vertices.append(point)
            return index[point]

        for triangle in triangles:
            if not polygon.covers(triangle):
                continue
            coords = list(triangle.exterior.coords)[:-1]
            bottom = [vertex((float(x), float(y), bottom_z)) for x, y in coords]
            top = [vertex((float(x), float(y), top_z)) for x, y in coords]
            faces.extend((tuple(reversed(bottom)), tuple(top)))

        boundary = list(slab.boundary)
        for first, second in zip(boundary, (*boundary[1:], boundary[0])):
            lower_a = vertex((first.x, first.y, bottom_z))
            lower_b = vertex((second.x, second.y, bottom_z))
            upper_a = vertex((first.x, first.y, top_z))
            upper_b = vertex((second.x, second.y, top_z))
            faces.append((lower_a, lower_b, upper_b, upper_a))

        if not faces:
            raise ValueError(f"slab {slab.id} has no triangulatable area")
        result.append(_mesh(slab.id, "slab", source_hash, tuple(vertices), tuple(faces)))
    return result


def _polygon(boundary: Any, element_id: str) -> Polygon:
    polygon = Polygon([(point.x, point.y) for point in boundary])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError(f"{element_id} boundary is not a valid positive-area polygon")
    return polygon


def _mesh(element_id: str, element_type: str, source_hash: str, vertices: Any, faces: Any) -> DerivedMesh:
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
