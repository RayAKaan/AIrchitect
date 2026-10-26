from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .authority import GeometrySource


@dataclass(frozen=True)
class GeometryIdentity:
    """Immutable identity for a geometry artifact and its canonical inputs."""

    organization_id: str
    project_id: str
    project_version_id: str
    world_model_revision_id: str
    world_model_hash: str
    design_alternative_id: str
    design_hash: str
    source: GeometrySource
    geometry_hash: str

    def payload(self) -> dict[str, str]:
        return {
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "project_version_id": self.project_version_id,
            "world_model_revision_id": self.world_model_revision_id,
            "world_model_hash": self.world_model_hash,
            "design_alternative_id": self.design_alternative_id,
            "design_hash": self.design_hash,
            "source": self.source.value,
            "geometry_hash": self.geometry_hash,
        }

    @property
    def identity_hash(self) -> str:
        canonical = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_geometry_identity(values: dict[str, Any]) -> GeometryIdentity:
    """Construct an identity while rejecting missing or blank provenance."""
    required = (
        "organization_id",
        "project_id",
        "project_version_id",
        "world_model_revision_id",
        "world_model_hash",
        "design_alternative_id",
        "design_hash",
        "source",
        "geometry_hash",
    )
    missing = [key for key in required if not str(values.get(key, "")).strip()]
    if missing:
        raise ValueError(f"missing geometry identity fields: {', '.join(missing)}")

    return GeometryIdentity(
        organization_id=str(values["organization_id"]),
        project_id=str(values["project_id"]),
        project_version_id=str(values["project_version_id"]),
        world_model_revision_id=str(values["world_model_revision_id"]),
        world_model_hash=str(values["world_model_hash"]),
        design_alternative_id=str(values["design_alternative_id"]),
        design_hash=str(values["design_hash"]),
        source=GeometrySource(values["source"]),
        geometry_hash=str(values["geometry_hash"]),
    )
