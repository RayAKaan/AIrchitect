"""Deterministic projection from the canonical architectural model to CAD input."""

from __future__ import annotations

from app.domains.cad.protocol import CadJobRequest, Footprint, MassingElement
from app.domains.model import ArchitecturalModel, Level, Space, model_hash


def build_cad_request(
    model: ArchitecturalModel,
    *,
    job_id: str = "",
    alternative_ref: str = "",
    project_name: str = "AIrchitect Project",
) -> CadJobRequest:
    """Project canonical spaces into bounded CAD massing elements.

    This adapter is deliberately one-way: CAD geometry cannot become a second
    source of truth. Every emitted element carries the canonical model hash.
    """
    levels = {level.id: level for level in model.levels}
    elements: list[MassingElement] = []
    for space in sorted(model.spaces, key=lambda item: item.id):
        level = _require_level(levels, space.level_id)
        points = [(point.x, point.y) for point in space.boundary]
        elements.append(
            MassingElement(
                id=space.id,
                kind="building_mass",
                name=space.name,
                footprint=Footprint(points=points),
                base_elevation_m=level.elevation_m,
                height_m=level.height_m,
                storey_index=_level_index(model.levels, level.id),
                material_class="canonical_space",
                source_reference=model_hash(model),
                metadata={"canonical_element_type": "space", "level_id": level.id},
            )
        )

    if not elements:
        raise ValueError("canonical model contains no spaces to project into CAD")

    return CadJobRequest(
        schema_version="1.0",
        job_id=job_id,
        alternative_ref=alternative_ref,
        project_name=project_name,
        elements=elements,
        site=Footprint(points=[
            (model.site.origin.x, model.site.origin.y),
            (model.site.origin.x + model.site.width_m, model.site.origin.y),
            (model.site.origin.x + model.site.width_m, model.site.origin.y + model.site.depth_m),
            (model.site.origin.x, model.site.origin.y + model.site.depth_m),
        ]),
    )


def _require_level(levels: dict[str, Level], level_id: str) -> Level:
    try:
        return levels[level_id]
    except KeyError as exc:
        raise ValueError(f"space references unknown level {level_id!r}") from exc


def _level_index(levels: tuple[Level, ...], level_id: str) -> int:
    ordered = sorted(levels, key=lambda item: (item.elevation_m, item.id))
    for index, level in enumerate(ordered):
        if level.id == level_id:
            return index
    raise ValueError(f"unknown level {level_id!r}")


__all__ = ["build_cad_request"]
