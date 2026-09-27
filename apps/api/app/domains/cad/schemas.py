"""Request and response bodies for the CAD/BIM API.

The request surface is intentionally tiny. A client names a design alternative and
may narrow the outputs it wants; everything else -- the world model, the design
parameters, the geometry the kernel should build -- is resolved server-side from
the alternative. Accepting a footprint or a set of dimensions here would create a
second source of geometry for a project version, one that no constraint, no
world model, and no audit record had ever seen.

The response bodies are read models over persisted state. They report the
provenance of a run (which provider, which engine version, which world model
revision) because a geometric number without its provenance is not reviewable, and
they report staleness explicitly rather than letting a consumer infer it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.db.models import CadArtifact, CadJobRun


class CadGenerationRequest(BaseModel):
    """Ask for real geometry for a design alternative."""

    #: Narrows the artifact set. Omit to get everything the deployment enables.
    #: These values can only ever remove outputs, never add one the deployment has
    #: turned off.
    requested_outputs: list[Literal["glb", "step", "ifc", "freecad_document"]] | None = None


class CadErrorBody(BaseModel):
    code: str
    message: str


class CadMeasurementBody(BaseModel):
    """One solid's measurements, as read back from the B-rep.

    Every field here was measured on a real solid. There is no ``gross_floor_area``
    or ``coverage`` because the kernel does not produce them; see
    :mod:`app.domains.cad.protocol` for the full measurement contract.
    """

    id: str
    kind: str
    volume_m3: float
    surface_area_m2: float
    centroid: tuple[float, float, float]
    bounding_box: dict[str, Any]
    solid_count: int
    face_count: int
    edge_count: int
    vertex_count: int
    is_valid: bool
    is_closed: bool
    center_of_mass: tuple[float, float, float] | None = None


class CadArtifactBody(BaseModel):
    id: str
    kind: str
    filename: str
    content_type: str
    byte_size: int
    sha256: str
    media_role: str
    #: Relative, opaque. The caller resolves it through the download endpoint; the
    #: store's real path on the server is never exposed.
    storage_key: str
    download_path: str
    created_at: datetime


class CadJobBody(BaseModel):
    id: str
    status: str
    provider: str
    provider_engine_name: str
    provider_engine_version: str
    occt_version: str
    ifc_library_version: str
    freecad_version: str | None
    request_hash: str
    element_count: int
    job_id: str
    design_alternative_id: str | None
    geometry_artifact_id: str | None
    world_model_revision_id: str | None
    input_world_model_hash: str
    #: True when the world model moved while the worker was running, so this result
    #: was recorded stale. Consumers must not treat a stale run's measurements as
    #: describing the current project.
    stale: bool
    duration_ms: int | None
    error: CadErrorBody | None
    warnings: list[str]
    measurements: dict[str, Any]
    validation: dict[str, Any]
    toolchain: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    #: Advisory only. The numbers are exact for the solid that was built, which is
    #: a conceptual mass; they are not a construction quantity.
    notice: str


MEASUREMENT_NOTICE = (
    "Measurements are read from a solid built to the design alternative's parameters. "
    "They are exact for that solid and are not a construction quantity."
)


def artifact_out(row: CadArtifact, version_id: str) -> CadArtifactBody:
    return CadArtifactBody(
        id=row.id,
        kind=row.kind,
        filename=row.filename,
        content_type=row.content_type,
        byte_size=row.byte_size,
        sha256=row.sha256,
        media_role=row.media_role,
        storage_key=row.storage_key,
        download_path=f"/api/v1/projects/{row.project_id}/versions/{version_id}"
        f"/cad/artifacts/{row.id}/download",
        created_at=row.created_at,
    )


def job_out(
    row: CadJobRun,
    *,
    current_hash: str,
    stale: bool | None = None,
) -> CadJobBody:
    """Render a run.

    ``current_hash`` lets a stale run be reported even if the cascade has not
    rewritten its status yet, so a consumer never sees a superseded result reading
    as current between the world model change and the next design generation.
    """
    is_stale = stale if stale is not None else (
        row.status == "STALE"
        or (row.input_world_model_hash != current_hash and row.status == "SUCCEEDED")
    )
    return CadJobBody(
        id=row.id,
        status="STALE" if is_stale and row.status == "SUCCEEDED" else row.status,
        provider=row.provider,
        provider_engine_name=row.provider_engine_name,
        provider_engine_version=row.provider_engine_version,
        occt_version=row.occt_version,
        ifc_library_version=row.ifc_library_version,
        freecad_version=row.freecad_version,
        request_hash=row.request_hash,
        element_count=row.element_count,
        job_id=row.job_id,
        design_alternative_id=row.design_alternative_id,
        geometry_artifact_id=row.geometry_artifact_id,
        world_model_revision_id=row.world_model_revision_id,
        input_world_model_hash=row.input_world_model_hash,
        stale=is_stale,
        duration_ms=row.duration_ms,
        error=(
            CadErrorBody(code=row.error_code, message=row.error_message or "")
            if row.error_code
            else None
        ),
        warnings=list(row.warnings_json or []),
        measurements=dict(row.measurements_json or {}),
        validation=dict(row.validation_json or {}),
        toolchain=dict(row.capabilities_json or {}),
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        notice=MEASUREMENT_NOTICE,
    )


__all__ = [
    "CadArtifactBody",
    "CadErrorBody",
    "CadGenerationRequest",
    "CadJobBody",
    "CadMeasurementBody",
    "artifact_out",
    "job_out",
]
