from __future__ import annotations

import math
from dataclasses import dataclass

from .schemas import ArchitecturalModel, Point3D


@dataclass(frozen=True)
class RotateElement:
    element_id: str
    angle_deg: float


@dataclass(frozen=True)
class ResizeElement:
    element_id: str
    scale: float


def _validate_element_id(element_id: str) -> None:
    if not element_id:
        raise ValueError("element_id is required")


def _rotate(point: Point3D, angle_rad: float, center: Point3D) -> Point3D:
    dx, dy = point.x - center.x, point.y - center.y
    cosine, sine = math.cos(angle_rad), math.sin(angle_rad)
    return Point3D(x=center.x + dx * cosine - dy * sine, y=center.y + dx * sine + dy * cosine, z=point.z)


def _centroid(points: tuple[Point3D, ...]) -> Point3D:
    return Point3D(x=sum(point.x for point in points) / len(points), y=sum(point.y for point in points) / len(points), z=points[0].z)


def rotate_element(model: ArchitecturalModel, command: RotateElement) -> ArchitecturalModel:
    _validate_element_id(command.element_id)
    if not math.isfinite(command.angle_deg):
        raise ValueError("rotation angle must be finite")
    angle_rad = math.radians(command.angle_deg)
    spaces, walls, slabs = list(model.spaces), list(model.walls), list(model.slabs)
    found = False
    for index, element in enumerate(spaces):
        if element.id == command.element_id:
            center = _centroid(element.boundary)
            spaces[index] = element.model_copy(update={"boundary": tuple(_rotate(p, angle_rad, center) for p in element.boundary)})
            found = True
            break
    if not found:
        for index, element in enumerate(slabs):
            if element.id == command.element_id:
                center = _centroid(element.boundary)
                slabs[index] = element.model_copy(update={"boundary": tuple(_rotate(p, angle_rad, center) for p in element.boundary)})
                found = True
                break
    if not found:
        for index, element in enumerate(walls):
            if element.id == command.element_id:
                center = Point3D(x=(element.start.x + element.end.x) / 2, y=(element.start.y + element.end.y) / 2, z=element.start.z)
                walls[index] = element.model_copy(update={"start": _rotate(element.start, angle_rad, center), "end": _rotate(element.end, angle_rad, center)})
                found = True
                break
    if not found:
        raise ValueError(f"element {command.element_id!r} is not a supported geometric element")
    return model.model_copy(update={"revision": model.revision + 1, "spaces": tuple(spaces), "walls": tuple(walls), "slabs": tuple(slabs)})


def resize_element(model: ArchitecturalModel, command: ResizeElement) -> ArchitecturalModel:
    _validate_element_id(command.element_id)
    if not math.isfinite(command.scale) or command.scale <= 0:
        raise ValueError("scale must be finite and greater than zero")
    spaces, walls, slabs = list(model.spaces), list(model.walls), list(model.slabs)
    found = False
    for index, element in enumerate(spaces):
        if element.id == command.element_id:
            center = _centroid(element.boundary)
            spaces[index] = element.model_copy(update={"boundary": tuple(Point3D(x=center.x + (p.x - center.x) * command.scale, y=center.y + (p.y - center.y) * command.scale, z=p.z) for p in element.boundary)})
            found = True
            break
    if not found:
        for index, element in enumerate(slabs):
            if element.id == command.element_id:
                center = _centroid(element.boundary)
                slabs[index] = element.model_copy(update={"boundary": tuple(Point3D(x=center.x + (p.x - center.x) * command.scale, y=center.y + (p.y - center.y) * command.scale, z=p.z) for p in element.boundary), "thickness_m": element.thickness_m * command.scale})
                found = True
                break
    if not found:
        for index, element in enumerate(walls):
            if element.id == command.element_id:
                center = Point3D(x=(element.start.x + element.end.x) / 2, y=(element.start.y + element.end.y) / 2, z=element.start.z)
                walls[index] = element.model_copy(update={"start": Point3D(x=center.x + (element.start.x - center.x) * command.scale, y=center.y + (element.start.y - center.y) * command.scale, z=element.start.z), "end": Point3D(x=center.x + (element.end.x - center.x) * command.scale, y=center.y + (element.end.y - center.y) * command.scale, z=element.end.z), "thickness_m": element.thickness_m * command.scale})
                found = True
                break
    if not found:
        raise ValueError(f"element {command.element_id!r} is not a supported geometric element")
    return model.model_copy(update={"revision": model.revision + 1, "spaces": tuple(spaces), "walls": tuple(walls), "slabs": tuple(slabs)})
