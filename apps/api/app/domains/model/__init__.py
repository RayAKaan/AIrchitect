"""Canonical architectural model domain.

The model is the authoritative, parametric representation of a building. Geometry,
artifacts, quantities, and downstream projections are derived from this state;
callers must not persist presentation-only geometry as the source of truth.
"""

from .identity import canonical_model_bytes, canonical_model_payload, model_hash
from .schemas import (
    ArchitecturalModel,
    Building,
    Door,
    Level,
    ModelElement,
    ModelMetadata,
    Point3D,
    Site,
    Slab,
    Space,
    Stair,
    Wall,
    Window,
)

__all__ = [
    "ArchitecturalModel",
    "Building",
    "Door",
    "Level",
    "ModelElement",
    "ModelMetadata",
    "Point3D",
    "Site",
    "Slab",
    "Space",
    "Stair",
    "Wall",
    "Window",
    "canonical_model_bytes",
    "canonical_model_payload",
    "model_hash",
]
