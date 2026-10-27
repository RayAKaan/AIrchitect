from __future__ import annotations

import math
from dataclasses import dataclass

from app.domains.model import ArchitecturalModel, Building, Level, Point3D, Site, Space

from .intent import AdjacencyRequirement, DesignIntent, RoomRequirement


@dataclass(frozen=True)
class DesignCompilationWarning:
    code: str
    message: str
    room_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DesignCompilation:
    model: ArchitecturalModel
    warnings: tuple[DesignCompilationWarning, ...]


def compile_design_intent(intent: DesignIntent) -> DesignCompilation:
    """Compile a validated design intent without invoking an LLM or mutating state."""
    site = Site(id=intent.site_id, width_m=intent.site_width_m, depth_m=intent.site_depth_m)
    building = Building(id="building-1", name="Primary Building", site_id=site.id)
    levels = tuple(
        Level(
            id=f"level-{index}",
            building_id=building.id,
            name="Ground" if index == 0 else f"Level {index}",
            elevation_m=index * intent.floor_to_floor_m,
            height_m=intent.floor_to_floor_m,
        )
        for index in range(intent.floors)
    )
    rooms_by_level = _group_rooms(intent.rooms)
    spaces: list[Space] = []
    warnings: list[DesignCompilationWarning] = []
    buildable_width = intent.site_width_m - intent.setback_left_m - intent.setback_right_m
    buildable_depth = intent.site_depth_m - intent.setback_front_m - intent.setback_rear_m

    for level_index, rooms in rooms_by_level.items():
        level = levels[level_index]
        cursor_x = intent.setback_left_m
        cursor_y = intent.setback_front_m
        row_depth = 0.0
        placements: dict[str, tuple[float, float, float, float]] = {}
        for room in _ordered_rooms(rooms, intent.adjacencies):
            width, depth = _room_dimensions(room, buildable_width, buildable_depth)
            if cursor_x + width > intent.setback_left_m + buildable_width + 1e-9:
                cursor_x = intent.setback_left_m
                cursor_y += row_depth
                row_depth = 0.0
            if cursor_y + depth > intent.setback_front_m + buildable_depth + 1e-9:
                raise ValueError(f"room program does not fit on level {level_index}: {room.room_id}")
            placements[room.room_id] = (cursor_x, cursor_y, width, depth)
            spaces.append(_space_from_placement(room, level, cursor_x, cursor_y, width, depth))
            cursor_x += width
            row_depth = max(row_depth, depth)

        warnings.extend(_check_adjacencies(rooms, placements, intent.adjacencies))

    model = ArchitecturalModel(
        project_id=intent.project_id,
        revision=1,
        site=site,
        buildings=(building,),
        levels=levels,
        spaces=tuple(spaces),
    )
    return DesignCompilation(model=model, warnings=tuple(warnings))


def _group_rooms(rooms: tuple[RoomRequirement, ...]) -> dict[int, tuple[RoomRequirement, ...]]:
    grouped: dict[int, list[RoomRequirement]] = {}
    for room in rooms:
        grouped.setdefault(room.level_index, []).append(room)
    return {level: tuple(items) for level, items in grouped.items()}


def _ordered_rooms(rooms: tuple[RoomRequirement, ...], adjacencies: tuple[AdjacencyRequirement, ...]) -> tuple[RoomRequirement, ...]:
    adjacency_score = {room.room_id: 0 for room in rooms}
    for requirement in adjacencies:
        if requirement.first_room_id in adjacency_score:
            adjacency_score[requirement.first_room_id] += requirement.priority
        if requirement.second_room_id in adjacency_score:
            adjacency_score[requirement.second_room_id] += requirement.priority
    return tuple(sorted(rooms, key=lambda room: (-adjacency_score[room.room_id], -room.target_area_m2, room.room_id)))


def _room_dimensions(room: RoomRequirement, max_width: float, max_depth: float) -> tuple[float, float]:
    width = min(max_width, max(1.5, math.sqrt(room.target_area_m2)))
    depth = room.target_area_m2 / width
    if depth > max_depth:
        depth = max_depth
        width = room.target_area_m2 / depth
    if width > max_width + 1e-9 or depth > max_depth + 1e-9:
        raise ValueError(f"room {room.room_id} cannot fit within the buildable envelope")
    return width, depth


def _space_from_placement(room: RoomRequirement, level: Level, x: float, y: float, width: float, depth: float) -> Space:
    z = level.elevation_m
    return Space(
        id=f"space-{room.room_id}",
        name=room.name,
        level_id=level.id,
        min_area_m2=room.min_area_m2 or 0,
        boundary=(
            Point3D(x=x, y=y, z=z),
            Point3D(x=x + width, y=y, z=z),
            Point3D(x=x + width, y=y + depth, z=z),
            Point3D(x=x, y=y + depth, z=z),
        ),
    )


def _check_adjacencies(
    rooms: tuple[RoomRequirement, ...],
    placements: dict[str, tuple[float, float, float, float]],
    requirements: tuple[AdjacencyRequirement, ...],
) -> list[DesignCompilationWarning]:
    room_ids = {room.room_id for room in rooms}
    warnings: list[DesignCompilationWarning] = []
    for requirement in requirements:
        if requirement.first_room_id not in room_ids or requirement.second_room_id not in room_ids:
            continue
        first = placements[requirement.first_room_id]
        second = placements[requirement.second_room_id]
        distance = _rectangle_distance(first, second)
        satisfied = {
            "adjacent": distance <= 1e-9,
            "near": distance <= 1.0,
            "separate": distance > 1e-9,
        }[requirement.relationship]
        if not satisfied:
            warnings.append(
                DesignCompilationWarning(
                    code="adjacency_unmet",
                    message=f"Could not satisfy {requirement.relationship} relationship between "
                    f"{requirement.first_room_id} and {requirement.second_room_id}.",
                    room_ids=(requirement.first_room_id, requirement.second_room_id),
                )
            )
    return warnings


def _rectangle_distance(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    dx = max(bx - (ax + aw), ax - (bx + bw), 0.0)
    dy = max(by - (ay + ah), ay - (by + bh), 0.0)
    return math.hypot(dx, dy)
