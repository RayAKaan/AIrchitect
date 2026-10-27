from __future__ import annotations

from app.domains.model import model_hash
from app.domains.model.schemas import ArchitecturalModel, Door, Window


_LAYER_BY_TYPE = {
    "wall": "AI_WALL",
    "door": "AI_DOOR",
    "window": "AI_WINDOW",
    "slab": "AI_SLAB",
    "space": "AI_SPACE",
}


def _pair(code: int, value: object) -> str:
    return f"{code}\n{value}\n"


def _line(parts: list[str], layer: str, x1: float, y1: float, x2: float, y2: float) -> None:
    parts.extend([
        _pair(0, "LINE"), _pair(8, layer),
        _pair(10, f"{x1:.6f}"), _pair(20, f"{y1:.6f}"),
        _pair(11, f"{x2:.6f}"), _pair(21, f"{y2:.6f}"),
    ])


def _polyline(parts: list[str], layer: str, points: list[tuple[float, float]]) -> None:
    if len(points) < 3:
        return
    parts.extend([_pair(0, "LWPOLYLINE"), _pair(8, layer), _pair(90, len(points)), _pair(70, 1)])
    for x, y in points:
        parts.extend([_pair(10, f"{x:.6f}"), _pair(20, f"{y:.6f}")])


def _wall_point(wall, distance: float) -> tuple[float, float]:
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 0:
        raise ValueError(f"wall {wall.id} has zero length")
    ratio = min(max(distance / length, 0.0), 1.0)
    return wall.start.x + dx * ratio, wall.start.y + dy * ratio


def _opening_line(parts: list[str], layer: str, opening: Door | Window, wall) -> None:
    center = _wall_point(wall, opening.offset_m)
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    length = (dx * dx + dy * dy) ** 0.5
    ux, uy = dx / length, dy / length
    half = opening.width_m / 2.0
    _line(parts, layer, center[0] - ux * half, center[1] - uy * half, center[0] + ux * half, center[1] + uy * half)


def render_dxf(model: ArchitecturalModel) -> bytes:
    """Render the canonical model to deterministic ASCII DXF R12-compatible linework."""
    digest = model_hash(model)
    parts: list[str] = [
        _pair(0, "SECTION"), _pair(2, "HEADER"), _pair(9, "$ACADVER"), _pair(1, "AC1009"),
        _pair(9, "$INSUNITS"), _pair(70, 6),
        _pair(999, f"AIrchitect revision={model.revision} hash={digest}"),
        _pair(0, "ENDSEC"), _pair(0, "SECTION"), _pair(2, "ENTITIES"),
    ]
    for wall in sorted(model.walls, key=lambda item: item.id):
        _line(parts, _LAYER_BY_TYPE["wall"], wall.start.x, wall.start.y, wall.end.x, wall.end.y)
    walls = {wall.id: wall for wall in model.walls}
    for opening in sorted((*model.doors, *model.windows), key=lambda item: item.id):
        wall = walls.get(opening.host_wall_id)
        if wall is None:
            raise ValueError(f"opening {opening.id} references missing wall {opening.host_wall_id}")
        _opening_line(parts, _LAYER_BY_TYPE[opening.element_type], opening, wall)
    for slab in sorted(model.slabs, key=lambda item: item.id):
        _polyline(parts, _LAYER_BY_TYPE["slab"], [(p.x, p.y) for p in slab.boundary])
    for space in sorted(model.spaces, key=lambda item: item.id):
        _polyline(parts, _LAYER_BY_TYPE["space"], [(p.x, p.y) for p in space.boundary])
    parts.extend([_pair(0, "ENDSEC"), _pair(0, "EOF")])
    return "".join(parts).encode("ascii")


def dxf_metadata(model: ArchitecturalModel) -> dict[str, object]:
    return {
        "format": "DXF-R12",
        "units": model.metadata.units,
        "model_revision": model.revision,
        "model_hash": model_hash(model),
        "wall_count": len(model.walls),
        "door_count": len(model.doors),
        "window_count": len(model.windows),
        "slab_count": len(model.slabs),
        "space_count": len(model.spaces),
    }
