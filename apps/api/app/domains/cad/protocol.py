"""Wire contract between the API and the CAD/BIM worker.

The API process and the worker process exchange plain JSON over a pipe. That is a
deliberate constraint, not an accident:

* the worker virtualenv contains only CAD packages and their dependencies, and
  pulling pydantic (and FastAPI's dependency tree) into it would enlarge the
  native-code surface we have to audit for the LGPL boundary;
* JSON is trivially inspectable, which matters when a job fails and the only
  evidence is a log line.

Because the two sides cannot share a model class, the API validates requests with
pydantic and the worker parses them with stdlib dataclasses. That duplication is
guarded by ``tests/test_phase18_worker_protocol.py``, which asserts the two
definitions have identical field sets -- so drift is a test failure rather than a
production incident.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# Artifact kinds the worker may emit. Extension is implied by kind; the API
# refuses anything outside this set, which is what stops a job from writing
# arbitrary files into the artifact root.
ArtifactKind = Literal["freecad_document", "step", "ifc", "glb", "brep"]

ARTIFACT_EXTENSIONS: dict[str, str] = {
    "freecad_document": ".FCStd",
    "step": ".step",
    "ifc": ".ifc",
    "glb": ".glb",
    "brep": ".brep",
}

#: Extensions the worker is permitted to write, case-insensitively.
ALLOWED_ARTIFACT_SUFFIXES: frozenset[str] = frozenset(
    ext.lower() for ext in ARTIFACT_EXTENSIONS.values()
)

MassingKind = Literal["building_mass", "floor_plate", "core", "site_boundary"]


class Footprint(BaseModel):
    """A closed 2D outline in metres, in the site's local X/Y plane.

    ``points`` is an ordered ring with no repeated closing point. The worker
    rejects rings with fewer than three distinct vertices, rings that are
    self-intersecting, and rings with a near-zero enclosed area, so those checks
    are enforced once, centrally, rather than in every provider.
    """

    points: list[tuple[float, float]] = Field(min_length=3, max_length=512)

    @field_validator("points")
    @classmethod
    def _finite(cls, value: list[tuple[float, float]]) -> list[tuple[float, float]]:
        for x, y in value:
            if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                raise ValueError("footprint coordinates must be numeric")
            if x != x or y != y or x in (float("inf"), float("-inf")) or y in (
                float("inf"),
                float("-inf"),
            ):
                raise ValueError("footprint coordinates must be finite")
        return [(float(x), float(y)) for x, y in value]

    @property
    def is_clockwise(self) -> bool:
        """Return True when the ring winds clockwise (negative signed area)."""
        return signed_area(self.points) < 0


def signed_area(points: list[tuple[float, float]] | list[Any]) -> float:
    """Return the signed area of a polygon ring using the shoelace formula.

    Sign encodes winding order, which OCCT honours when building faces, so this
    is used to normalise every ring to counter-clockwise before extrusion.
    """
    total = 0.0
    count = len(points)
    for index in range(count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % count]
        total += x1 * y2 - x2 * y1
    return total / 2.0


class MassingElement(BaseModel):
    """One prismatic massing element to be realised as a real solid."""

    id: str = Field(min_length=1, max_length=128)
    kind: MassingKind = "building_mass"
    name: str = Field(default="", max_length=256)
    footprint: Footprint
    base_elevation_m: float = 0.0
    height_m: float = Field(gt=0.0, le=1000.0)
    storey_index: int | None = None
    material_class: str = Field(default="conceptual_mass", max_length=128)
    source_reference: str = Field(default="", max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "name", "material_class", "source_reference")
    @classmethod
    def _no_control_chars(cls, value: str) -> str:
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("text fields must not contain control characters")
        return value


class CadJobTolerances(BaseModel):
    """Acceptance tolerances handed to the worker and echoed into provenance."""

    volume_tolerance_ratio: float = Field(default=0.005, gt=0.0, le=0.5)
    area_tolerance_ratio: float = Field(default=0.005, gt=0.0, le=0.5)
    linear_tolerance_m: float = Field(default=0.01, gt=0.0, le=10.0)


class CadJobOptions(BaseModel):
    """Which artifacts the worker should produce.

    Toggling these off is how the API keeps interactive requests fast while still
    producing a full artifact set for accepted alternatives.
    """

    write_fcstd: bool = True
    write_step: bool = True
    write_ifc: bool = True
    write_glb: bool = True
    # Named run_validation, not validate: a field called "validate" shadows
    # BaseModel.validate, which pydantic defines as a classmethod, and the
    # shadowing breaks model-level validation helpers.
    run_validation: bool = True
    ifc_schema: str = "IFC4"


class CadJobRequest(BaseModel):
    """A single bounded geometry job.

    One request produces geometry for exactly one design alternative, so a
    pathological alternative cannot monopolise a worker.
    """

    schema_version: str = "1.0"
    job_id: str = Field(default="", max_length=128)
    alternative_ref: str = Field(default="", max_length=128)
    project_name: str = Field(default="AIrchitect Project", max_length=256)
    elements: list[MassingElement] = Field(min_length=1, max_length=2000)
    tolerances: CadJobTolerances = Field(default_factory=CadJobTolerances)
    options: CadJobOptions = Field(default_factory=CadJobOptions)
    mesh_deflection_m: float = Field(default=0.05, gt=0.0, le=5.0)
    mesh_angular_deflection_rad: float = Field(default=0.35, gt=0.0, le=3.15)
    # Absolute directory the worker may write into. The API supplies this after
    # validating it is inside the configured artifact root; the worker refuses
    # to run at all if the directory escapes its sandbox root.
    output_dir: str = Field(default="", max_length=1024)
    sandbox_root: str = Field(default="", max_length=1024)
    site: Footprint | None = None
    # Bounds the worker's *inner* FreeCAD subprocess. The runner separately
    # enforces an outer wall-clock limit, and the two are not interchangeable: an
    # outer kill ends the whole job, while this one lets the worker report a
    # partial failure through the normal response document. The API stamps this
    # from cad_freecad_timeout_seconds; without it the worker would fall back to
    # its own default and the setting would appear to do nothing.
    freecad_timeout_seconds: float = Field(default=180.0, gt=0.0, le=3600.0)


class SolidMeasurement(BaseModel):
    """Measurements read back from a real B-rep solid, never assumed."""

    id: str
    kind: MassingKind
    volume_m3: float
    surface_area_m2: float
    centroid: tuple[float, float, float]
    bounding_box: BoundingBox
    solid_count: int
    face_count: int
    edge_count: int
    vertex_count: int
    is_valid: bool
    is_closed: bool
    center_of_mass: tuple[float, float, float] | None = None


class BoundingBox(BaseModel):
    """Axis-aligned bounding box in metres."""

    min: tuple[float, float, float]
    max: tuple[float, float, float]

    @property
    def size(self) -> tuple[float, float, float]:
        """Return the (x, y, z) extents."""
        return (
            self.max[0] - self.min[0],
            self.max[1] - self.min[1],
            self.max[2] - self.min[2],
        )


class ArtifactRef(BaseModel):
    """A file the worker produced, described by content hash rather than path.

    Paths are intentionally not part of this model: the API receives bytes, uploads
    them to object storage, and records only the hash. A worker that returned a
    filesystem path would tempt the API into trusting a worker-controlled path.
    """

    kind: ArtifactKind
    filename: str = Field(max_length=256)
    content_type: str
    byte_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: str = Field(default="", description="base64-encoded file content")


class ProviderInfo(BaseModel):
    """Which engine actually produced the geometry, and what it reported."""

    provider: str
    engine_name: str
    engine_version: str
    occt_version: str | None = None
    occt_build: str | None = None
    python_version: str
    ifc_library_version: str | None = None
    freecad_version: str | None = None
    provider_digest: str = Field(
        default="", description="SHA-256 over the executed provider source files"
    )


class ValidationCheck(BaseModel):
    """One machine-checkable geometry assertion and its outcome."""

    code: str
    status: Literal["PASS", "FAIL", "WARN", "SKIP"]
    actual: Any = None
    expected: Any = None
    detail: str = ""
    source: Literal["analytic", "solid", "provider"] = "solid"


class CadValidationResult(BaseModel):
    """Aggregate validation outcome, mixing analytic and solid-derived checks."""

    valid: bool
    checks: list[ValidationCheck] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CadJobResult(BaseModel):
    """What the worker returns to the API on success."""

    schema_version: str = "1.0"
    job_id: str = ""
    status: Literal["ok"] = "ok"
    provider: ProviderInfo
    measurements: list[SolidMeasurement]
    combined_volume_m3: float
    combined_area_m2: float
    combined_bounding_box: BoundingBox | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    validation: CadValidationResult | None = None
    element_count: int
    warnings: list[str] = Field(default_factory=list)


class CadJobFailure(BaseModel):
    """What the worker returns to the API on failure.

    The API turns this into a typed exception. ``detail`` is for operator logs
    only and is never returned verbatim to an API client, because CAD diagnostics
    routinely contain absolute paths.
    """

    schema_version: str = "1.0"
    job_id: str = ""
    status: Literal["error"] = "error"
    error_code: str
    message: str
    detail: str = ""
    provider: str = ""


__all__ = [
    "ALLOWED_ARTIFACT_SUFFIXES",
    "ARTIFACT_EXTENSIONS",
    "ArtifactKind",
    "ArtifactRef",
    "BoundingBox",
    "CadJobFailure",
    "CadJobOptions",
    "CadJobRequest",
    "CadJobResult",
    "CadJobTolerances",
    "CadValidationResult",
    "Footprint",
    "MassingElement",
    "MassingKind",
    "ProviderInfo",
    "SolidMeasurement",
    "ValidationCheck",
    "signed_area",
]
