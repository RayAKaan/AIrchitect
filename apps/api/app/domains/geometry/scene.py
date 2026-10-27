"""Stable 3D scene projection for interactive architectural viewers."""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.geometry.model_derivation import DerivedMesh, derive_model_meshes
from app.domains.model import ArchitecturalModel, model_hash


@dataclass(frozen=True)
class SceneNode:
    id: str
    element_type: str
    mesh_index: int
    source_model_hash: str
    geometry_hash: str


@dataclass(frozen=True)
class SceneBounds:
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]


@dataclass(frozen=True)
class ModelScene:
    model_hash: str
    nodes: tuple[SceneNode, ...]
    meshes: tuple[DerivedMesh, ...]
    bounds: SceneBounds


def build_model_scene(model: ArchitecturalModel) -> ModelScene:
    """Create a deterministic scene graph directly from canonical geometry."""
    meshes = derive_model_meshes(model)
    nodes = tuple(
        SceneNode(
            id=mesh.element_id,
            element_type=mesh.element_type,
            mesh_index=index,
            source_model_hash=mesh.source_model_hash,
            geometry_hash=mesh.geometry_hash,
        )
        for index, mesh in enumerate(meshes)
    )
    if not meshes:
        raise ValueError("model contains no renderable geometry")
    points = [point for mesh in meshes for point in mesh.vertices]
    minimum = tuple(min(point[index] for point in points) for index in range(3))
    maximum = tuple(max(point[index] for point in points) for index in range(3))
    return ModelScene(
        model_hash=model_hash(model),
        nodes=nodes,
        meshes=meshes,
        bounds=SceneBounds(minimum=minimum, maximum=maximum),
    )


__all__ = ["ModelScene", "SceneBounds", "SceneNode", "build_model_scene"]
