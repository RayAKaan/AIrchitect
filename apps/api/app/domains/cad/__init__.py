"""Phase 5 CAD/BIM domain.

This package is the *API side* of the CAD pipeline. It deliberately contains no
import of FreeCAD, OCCT, or IfcOpenShell. Every real geometry operation is
performed by a separate, bounded worker process whose code lives in
``app.cad_worker`` and which runs under its own virtualenv.

That separation is not stylistic. It is the mechanism that satisfies two
independent requirements at once:

* the API image stays small and free of native CAD dependencies, and
* the LGPL boundary asserted in ``docs/legal/PHASE-5-OPEN-SOURCE-LICENSE-AUDIT.md``
  is enforced by construction rather than by convention.

``test_dependency_isolation.py`` asserts that importing this package (or the API
application as a whole) cannot pull in a CAD or BIM library.
"""

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

__all__ = [
    "CadConfig",
    "DEFAULT_CAD_CONFIG",
    "CadDependencyMissingError",
    "CadJobError",
    "CadJobTimeoutError",
    "CadProviderError",
    "CadSecurityError",
    "GeometryEngineUnavailableError",
    "canonicalize",
    "semantic_hash",
]
