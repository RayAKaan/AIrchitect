from __future__ import annotations

from dataclasses import dataclass

from app.domains.model import model_hash
from app.domains.model.schemas import ArchitecturalModel


@dataclass(frozen=True, slots=True)
class IfcSemanticEntity:
    source_id: str
    ifc_class: str
    name: str
    level_id: str | None
    properties: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class IfcSemanticProjection:
    schema: str
    model_hash: str
    entities: tuple[IfcSemanticEntity, ...]
    relationships: tuple[tuple[str, str, str], ...]


def project_architectural_semantics(
    model: ArchitecturalModel, *, schema: str = "IFC4"
) -> IfcSemanticProjection:
    """Project canonical architectural entities into a deterministic IFC4 semantic graph."""
    if schema != "IFC4":
        raise ValueError("IFC_SCHEMA_UNSUPPORTED: only IFC4 is currently supported")
    entities: list[IfcSemanticEntity] = []
    for level in sorted(model.levels, key=lambda item: item.id):
        entities.append(
            IfcSemanticEntity(level.id, "IfcBuildingStorey", level.name, level.id, (("Elevation_m", str(level.elevation_m)),))
        )
    for space in sorted(model.spaces, key=lambda item: item.id):
        entities.append(
            IfcSemanticEntity(space.id, "IfcSpace", space.name, space.level_id, (("MinArea_m2", f"{space.min_area_m2:.6f}"),))
        )
    for wall in sorted(model.walls, key=lambda item: item.id):
        entities.append(
            IfcSemanticEntity(
                wall.id,
                "IfcWall",
                wall.name,
                wall.level_id,
                (("Thickness_m", f"{wall.thickness_m:.6f}"), ("Height_m", f"{wall.height_m:.6f}")),
            )
        )
    for door in sorted(model.doors, key=lambda item: item.id):
        entities.append(
            IfcSemanticEntity(
                door.id,
                "IfcDoor",
                door.name,
                door.level_id,
                (("Width_m", f"{door.width_m:.6f}"), ("Height_m", f"{door.height_m:.6f}")),
            )
        )
    for window in sorted(model.windows, key=lambda item: item.id):
        entities.append(
            IfcSemanticEntity(
                window.id,
                "IfcWindow",
                window.name,
                window.level_id,
                (("Width_m", f"{window.width_m:.6f}"), ("Height_m", f"{window.height_m:.6f}")),
            )
        )
    for slab in sorted(model.slabs, key=lambda item: item.id):
        entities.append(
            IfcSemanticEntity(
                slab.id,
                "IfcSlab",
                slab.name,
                slab.level_id,
                (("Thickness_m", f"{slab.thickness_m:.6f}"),),
            )
        )

    relationships: list[tuple[str, str, str]] = []
    for entity in entities:
        if entity.level_id and entity.source_id != entity.level_id:
            relationships.append(("CONTAINED_IN", entity.source_id, entity.level_id))
    for door in model.doors:
        relationships.append(("HOSTED_BY", door.id, door.host_wall_id))
    for window in model.windows:
        relationships.append(("HOSTED_BY", window.id, window.host_wall_id))

    return IfcSemanticProjection(
        schema=schema,
        model_hash=model_hash(model),
        entities=tuple(entities),
        relationships=tuple(sorted(relationships)),
    )
