"""Error taxonomy for the Phase 18 CAD/BIM pipeline.

Every failure mode a CAD worker can hit is mapped to a specific exception so the
API can distinguish "the toolchain is not installed" (an operator problem, 503)
from "the geometry is invalid" (a user problem, 422) from "the job blew its
time budget" (a resource problem, 504). Collapsing these into one exception is
what makes CAD pipelines undebuggable, because the three require completely
different responses.
"""

from __future__ import annotations


class CadError(Exception):
    """Base class for all CAD/BIM pipeline failures."""


class GeometryEngineUnavailableError(CadError):
    """The requested geometry engine is not compiled in or not enabled."""


class CadDependencyMissingError(CadError):
    """A required external toolchain component is absent or not executable.

    Raised when the worker virtualenv, FreeCAD, or a pinned CAD package cannot be
    located. This is an operator/environment fault, never a user input fault, and
    must not be reported to the caller as invalid input.
    """

    def __init__(self, component: str, detail: str = "") -> None:
        self.component = component
        self.detail = detail
        message = f"CAD dependency unavailable: {component}"
        if detail:
            message = f"{message} ({detail})"
        super().__init__(message)


class CadProviderError(CadError):
    """A CAD/BIM provider ran but reported a failure.

    Carries the provider's own diagnostics so they can be surfaced in the job
    record without leaking filesystem paths to API clients.
    """

    def __init__(
        self,
        provider: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        self.provider = provider
        self.details = details or {}
        super().__init__(f"{provider} failed: {message}")


class CadJobTimeoutError(CadError):
    """A worker exceeded its wall-clock budget and was terminated."""

    def __init__(self, provider: str, timeout_seconds: float) -> None:
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"{provider} exceeded its {timeout_seconds:g}s time budget and was terminated"
        )


class CadSecurityError(CadError):
    """A job request was rejected before execution for safety reasons.

    Covers path traversal, disallowed artifact extensions, oversized payloads, and
    any attempt to smuggle executable content through a job field.
    """


class CadJobError(CadError):
    """The worker returned a result the API could not accept.

    Indicates a protocol mismatch rather than a geometry problem; it is always a
    bug in AIrchitect rather than user input.
    """


class CadStorageError(CadError):
    """The artifact store rejected a key, a kind, or an object that failed its hash.

    A storage key originates in our own database, so a malformed one is an internal
    defect, not user input. It is deliberately not a ``CadSecurityError``: nothing
    here should be reported to a caller as a rejected request, and collapsing the
    two would make a corrupt row look like an attack.
    """


class CadArtifactMissingError(CadError):
    """A well-formed reference points at content that is no longer in the store.

    Usually means the artifact root was pruned, or restored from a backup that did
    not include the blobs. Kept distinct from ``CadStorageError`` because the two
    need different responses: this one becomes a non-disclosing 404, whereas a
    malformed key is a bug worth alerting on.
    """
