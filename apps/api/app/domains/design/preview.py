from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domains.geometry.model_derivation import DerivedMesh, derive_model_meshes
from app.domains.model import ArchitecturalModel

from .compiler import DesignCompilation, compile_design_intent
from .intent import DesignIntent
from .walls import with_generated_walls


class PreviewMesh(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    element_id: str
    element_type: str
    source_model_hash: str
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    geometry_hash: str


class ModelPreview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model: ArchitecturalModel
    geometry: tuple[PreviewMesh, ...]
    warnings: tuple[dict[str, object], ...]


def build_model_preview(intent: DesignIntent) -> ModelPreview:
    """Run the complete deterministic design -> model -> geometry projection."""
    compilation: DesignCompilation = compile_design_intent(intent)
    model = with_generated_walls(compilation.model)
    meshes = derive_model_meshes(model)
    return ModelPreview(
        model=model,
        geometry=tuple(_mesh_to_schema(mesh) for mesh in meshes),
        warnings=tuple(
            {"code": warning.code, "message": warning.message, "room_ids": warning.room_ids}
            for warning in compilation.warnings
        ),
    )


def _mesh_to_schema(mesh: DerivedMesh) -> PreviewMesh:
    return PreviewMesh(
        element_id=mesh.element_id,
        element_type=mesh.element_type,
        source_model_hash=mesh.source_model_hash,
        vertices=mesh.vertices,
        faces=mesh.faces,
        geometry_hash=mesh.geometry_hash,
    )
