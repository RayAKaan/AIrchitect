"""Pure deterministic transforms for canonical architectural model elements."""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import ArchitecturalModel, Point3D


@dataclass(frozen=True)
class TranslateElement:
    element_id: str
    dx_m: float
    dy_m: float
    dz_m: float


def _point(point: Point3D, command: TranslateElement) -> Point3D:
    return Point3D(x=point.x + command.dx_m, y=point.y + command.dy_m, z=point.z + command.dz_m)


def translate_element(model: ArchitecturalModel, command: TranslateElement) -> ArchitecturalModel:
    """Return a new valid model with one geometric element translated.

    The operation is intentionally pure: it never mutates the input model and
    always re-validates the complete canonical model before returning.
    """
    if not command.element_id:
        raise ValueError("element_id is required")
    if not all(__import__("math").isfinite(value) for value in (command.dx_m, command.dy_m, command.dz_m)):
        raise ValueError("translation values must be finite")

    def update_collection(collection: tuple[object, ...]) -> tuple[object, ...]:
        updated: list[object] = []
        found = False
        for item in collection:
            if getattr(item, "id", None) != command.element_id:
                updated.append(item)
                continue
            found = True
            if hasattr(item, "start") and hasattr(item, "end"):
                updated.append(item.model_copy(update={"start": _point(item.start, command), "end": _point(item.end, command)}))
            elif hasattr(item, "boundary"):
                updated.append(item.model_copy(update={"boundary": tuple(_point(point, command) for point in item.boundary)}))
            else:
                raise ValueError(f"element type {getattr(item, 'element_type', 'unknown')} is not translatable")
        return tuple(updated), found

    collections = (model.spaces, model.walls, model.slabs)
    replacements: list[tuple[object, ...]] = []
    found = False
    for collection in collections:
        replacement, collection_found = update_collection(collection)
        replacements.append(replacement)
        found = found or collection_found
    if not found:
        raise ValueError(f"element {command.element_id!r} is not a translatable geometric element")

    return model.model_copy(update={
        "revision": model.revision + 1,
        "spaces": replacements[0],
        "walls": replacements[1],
        "slabs": replacements[2],
    })
