from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GeometrySource(StrEnum):
    """Source classes for geometry artifacts.

    Only CAD_BREP is authoritative for engineering and presentation consumers.
    """

    CAD_BREP = "CAD_BREP"
    LEGACY_IR = "LEGACY_IR"


class GeometryAuthorityError(ValueError):
    """Raised when a geometry artifact cannot be used authoritatively."""


@dataclass(frozen=True)
class GeometryAuthorityInput:
    source: GeometrySource
    current: bool
    world_model_hash_matches: bool
    design_hash_matches: bool
    cad_run_succeeded: bool
    validation_document_present: bool


def require_authoritative_geometry(value: GeometryAuthorityInput) -> None:
    """Fail closed unless all canonical geometry requirements are satisfied."""
    if value.source is not GeometrySource.CAD_BREP:
        raise GeometryAuthorityError("CAD_REQUIRED")
    if not value.current:
        raise GeometryAuthorityError("GEOMETRY_STALE")
    if not value.world_model_hash_matches:
        raise GeometryAuthorityError("WORLD_MODEL_MISMATCH")
    if not value.design_hash_matches:
        raise GeometryAuthorityError("DESIGN_MISMATCH")
    if not value.cad_run_succeeded:
        raise GeometryAuthorityError("CAD_RUN_INVALID")
    if not value.validation_document_present:
        raise GeometryAuthorityError("CAD_VALIDATION_REQUIRED")
