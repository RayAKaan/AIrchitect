"""Deterministic projection from the canonical architectural model to CAD input."""

from __future__ import annotations

import math
from typing import Any

from app.domains.cad.protocol import CadJobRequest, Footprint, MassingElement
from app.domains.semantic_model.service import compile_parametric_geometry
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


def _wall_footprint(start: dict[str, Any], end: dict[str, Any], thickness_m: float) -> tuple[list[tuple[float, float]], float]:
    """Return the metric XY rectangle swept by a horizontal wall axis."""
    coordinates = [start.get(axis) for axis in ("x", "y", "z")] + [
        end.get(axis) for axis in ("x", "y", "z")
    ]
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(float(value)) for value in coordinates):
        raise ValueError("wall axis coordinates must be finite metric numbers")
    sx, sy, sz, ex, ey, ez = (float(value) for value in coordinates)
    if abs(ez - sz) > 1e-6:
        raise ValueError("WALL_AXIS_NON_HORIZONTAL")
    if isinstance(thickness_m, bool) or not isinstance(thickness_m, (int, float)) or not math.isfinite(float(thickness_m)) or thickness_m <= 0:
        raise ValueError("wall thickness must be a positive finite metric value")
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        raise ValueError("wall axis length must be greater than the geometry tolerance")
    half = float(thickness_m) / 2.0
    nx, ny = -dy / length * half, dx / length * half
    ring = [
        (sx + nx, sy + ny),
        (ex + nx, ey + ny),
        (ex - nx, ey - ny),
        (sx - nx, sy - ny),
    ]
    return ring, sz


def build_semantic_cad_request(
    world_model: dict[str, Any],
    semantic_model: dict[str, Any],
    *,
    job_id: str,
    project_name: str = "AIrchitect Project",
) -> CadJobRequest:
    """Compile reviewed canonical walls into real worker-ready prism inputs.

    The semantic World Model remains authoritative. Unsupported or incomplete
    element types are not approximated as massing; this adapter currently accepts
    only dimension-complete horizontal walls.
    """
    source_world_hash = semantic_model.get("source_world_model_hash")
    if (
        not isinstance(source_world_hash, str)
        or len(source_world_hash) != 64
        or any(character not in "0123456789abcdef" for character in source_world_hash.lower())
    ):
        raise ValueError("SEMANTIC_WORLD_MODEL_HASH_REQUIRED")
    specification = compile_parametric_geometry(world_model, semantic_model)
    semantic_hash = specification.get("semantic_model_hash")
    if (
        not isinstance(semantic_hash, str)
        or len(semantic_hash) != 64
        or any(character not in "0123456789abcdef" for character in semantic_hash.lower())
    ):
        raise ValueError("SEMANTIC_MODEL_HASH_INVALID")
    architectural_intents = [
        intent for intent in specification.get("intents", [])
        if intent.get("element_type") in {"Wall", "Slab"}
    ]
    if not architectural_intents:
        raise ValueError("SEMANTIC_ARCHITECTURAL_ELEMENTS_REQUIRED")
    if len(architectural_intents) > 2_000:
        raise ValueError("SEMANTIC_ARCHITECTURAL_ELEMENT_LIMIT_EXCEEDED")
    elements_by_id = {
        element["id"]: element for element in semantic_model.get("elements", [])
    }
    elements: list[MassingElement] = []
    for intent in walls:
        if intent.get("status") != "READY_FOR_CAD_ADAPTER":
            raise ValueError(
                f"SEMANTIC_WALL_UNDERCONSTRAINED:{intent.get('element_id')}:{','.join(intent.get('missing_parameters', []))}"
            )
        params = intent.get("parameters") or {}
        element_id = intent["element_id"]
        authored = elements_by_id.get(element_id)
        if authored is None:
            raise ValueError(f"SEMANTIC_ELEMENT_MISSING:{element_id}")
        placement = intent.get("placement") or {}
        element_type = intent["element_type"]
        if element_type == "Wall":
            start = params.get("start_m") or {}
            end = params.get("end_m") or {}
            footprint, base_elevation = _wall_footprint(
                start,
                end,
                params.get("thickness_m"),
            )
            axis_length = math.hypot(
                float(end["x"]) - float(start["x"]),
                float(end["y"]) - float(start["y"]),
            )
            declared_length = float(params["length_m"])
            if abs(axis_length - declared_length) > max(1e-4, axis_length * 1e-4):
                raise ValueError(f"WALL_LENGTH_MISMATCH:{element_id}")
            kind = "wall"
            height = float(params["height_m"])
            material_class = "architectural_wall"
        else:
            boundary = params.get("boundary_m")
            if not isinstance(boundary, list) or len(boundary) < 4:
                raise ValueError(f"SLAB_BOUNDARY_INVALID:{element_id}")
            points = [
                (float(point["x"]), float(point["y"]))
                for point in boundary
            ]
            elevations = [float(point["z"]) for point in boundary]
            if max(elevations) - min(elevations) > 1e-6:
                raise ValueError(f"SLAB_BOUNDARY_NON_PLANAR:{element_id}")
            if points[0] != points[-1]:
                raise ValueError(f"SLAB_BOUNDARY_NOT_CLOSED:{element_id}")
            from shapely.geometry import Polygon
            polygon = Polygon(points)
            if not polygon.is_valid or polygon.is_empty or polygon.interiors or polygon.area <= 1e-6:
                raise ValueError(f"SLAB_BOUNDARY_INVALID:{element_id}")
            declared_area = params.get("area_m2")
            if declared_area is not None and abs(polygon.area - float(declared_area)) > max(0.02, polygon.area * 1e-4):
                raise ValueError(f"SLAB_AREA_MISMATCH:{element_id}")
            footprint = points[:-1]
            height = float(params["thickness_m"])
            base_elevation = elevations[0] - height
            kind = "floor_plate"
            material_class = "architectural_slab"
        elements.append(MassingElement(
            id=element_id,
            kind=kind,
            name=authored.get("name") or element_type,
            footprint=Footprint(points=footprint),
            base_elevation_m=base_elevation,
            height_m=height,
            storey_index=placement.get("level_number"),
            material_class=material_class,
            source_reference=source_world_hash,
            metadata={
                "semantic_element_id": element_id,
                "element_type": element_type,
                "world_model_hash": source_world_hash,
                "semantic_model_hash": semantic_hash,
                "coordinate_system": "local_cartesian_z_up",
                "units": "m",
            },
        ))
    return CadJobRequest(
        schema_version="1.0",
        job_id=job_id,
        alternative_ref="",
        project_name=project_name,
        elements=elements,
    )


__all__ = ["build_cad_request", "build_semantic_cad_request"]
