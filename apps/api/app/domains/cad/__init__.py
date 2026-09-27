"""Phase 18 CAD/BIM domain.

This package is the *API side* of the CAD pipeline. It deliberately contains no
import of FreeCAD, OCCT, or IfcOpenShell. Every real geometry operation is
performed by a separate, bounded worker process whose code lives in
``app.cad_worker`` and which runs under its own virtualenv.

That separation is not stylistic. It is the mechanism that satisfies two
independent requirements at once:

* the API image stays small and free of native CAD dependencies, and
* the LGPL boundary asserted in ``docs/legal/PHASE-18-OPEN-SOURCE-LICENSE-AUDIT.md``
  is enforced by construction rather than by convention.

``test_phase18_isolation.py`` asserts that importing this package (or the API
application as a whole) cannot pull in a CAD or BIM library.

The entry point for callers is :func:`run_cad_job`; :class:`CadJobRequest` and
:class:`CadJobOptions` describe the request it accepts and
:class:`WorkerCapabilities` / :func:`probe_capabilities` describe the toolchain it
resolved that request against.
"""

from app.domains.cad.capability import (
    FreecadCapabilities,
    IfcCapabilities,
    KernelCapabilities,
    OcctCapabilities,
    WorkerCapabilities,
    probe_capabilities,
    reset_capability_cache,
)
from app.domains.cad.config import CadConfig, DEFAULT_CAD_CONFIG
from app.domains.cad.errors import (
    CadDependencyMissingError,
    CadJobError,
    CadJobTimeoutError,
    CadProviderError,
    CadSecurityError,
    GeometryEngineUnavailableError,
)
from app.domains.cad.hashing import canonicalize, semantic_hash
from app.domains.cad.protocol import (
    ArtifactRef,
    BoundingBox,
    CadJobOptions,
    CadJobRequest,
    CadJobResult,
    CadValidationResult,
    Footprint,
    MassingElement,
    ProviderInfo,
    SolidMeasurement,
    ValidationCheck,
)
from app.domains.cad.runner import run_cad_job

__all__ = [
    # Configuration
    "CadConfig",
    "DEFAULT_CAD_CONFIG",
    # Errors
    "CadDependencyMissingError",
    "CadJobError",
    "CadJobTimeoutError",
    "CadProviderError",
    "CadSecurityError",
    "GeometryEngineUnavailableError",
    # Hashing
    "canonicalize",
    "semantic_hash",
    # Request/result contract
    "ArtifactRef",
    "BoundingBox",
    "CadJobOptions",
    "CadJobRequest",
    "CadJobResult",
    "CadValidationResult",
    "Footprint",
    "MassingElement",
    "ProviderInfo",
    "SolidMeasurement",
    "ValidationCheck",
    # Capability discovery
    "FreecadCapabilities",
    "IfcCapabilities",
    "KernelCapabilities",
    "OcctCapabilities",
    "WorkerCapabilities",
    "probe_capabilities",
    "reset_capability_cache",
    # Execution
    "run_cad_job",
]
