"""Turn a design alternative into a real solid, and record what came back.

This is the seam between the three S9/S10 layers and the only place that knows how
they compose:

* :mod:`app.domains.cad.runner` knows how to run a bounded worker and validate
  what it says;
* :mod:`app.domains.cad.storage` knows how to put bytes on disk;
* :mod:`app.domains.cad.persistence` knows how to write the run, artifacts,
  geometry, validation, and evidence.

Keeping the composition out of ``routes.py`` means an HTTP caller is not the only
way to generate geometry, and it keeps the domain rules -- what a request may
contain, when a job is refused, how a timeout is recorded -- testable without a
client.

The mapping from an alternative to worker input
-----------------------------------------------

The client is not allowed to describe geometry. It names an alternative and the
server derives the solid from that alternative's own design parameters, because
the alternative is what the world model, the constraint resolver, and the
strategy all agreed on. Letting the client post a footprint would create a second,
unaudited source of geometry for the same project version.

One alternative becomes exactly one prismatic massing element. That is
deliberately modest: the design engine already reduced the problem to a
rectangular mass with a floor count, and asking the kernel to build that as a real
solid is what makes the downstream measurements real. Deriving more geometry than
the alternative actually contains would invent design decisions.

Failure is a recorded outcome, not an exception
------------------------------------------------

A worker that rejects the geometry, times out, or returns nonsense has still been
invoked, and the invocation is part of the audit trail. So a job that ran and did
not produce geometry is written as a ``FAILED`` run carrying its typed error code,
and the caller gets that run back rather than an opaque HTTP error. What is *not*
recorded is a job that never started because the toolchain is not installed --
there is no invocation to describe.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CadArtifact,
    CadJobRun,
    DesignAlternative,
    Project,
    ProjectVersion,
    WorldModelRevision,
)
from app.domains.cad.capability import WorkerCapabilities
from app.domains.cad.config import CadConfig
from app.domains.cad.errors import (
    CadDependencyMissingError,
    CadError,
    CadJobError,
    CadJobTimeoutError,
    CadProviderError,
    CadSecurityError,
    CadStorageError,
    GeometryEngineUnavailableError,
)
from app.domains.cad.persistence import (
    RecordedCadRun,
    record_cad_failure,
    record_cad_success,
    resolve_current_world,
    store_worker_artifacts,
)
from app.domains.cad.protocol import (
    ARTIFACT_EXTENSIONS,
    CadJobOptions,
    CadJobRequest,
    CadJobResult,
    Footprint,
    MassingElement,
)
from app.domains.cad.runner import run_cad_job
from app.domains.cad.storage import ContentAddressedStore, StoredBlob

logger = logging.getLogger(__name__)


def classify_failure(exc: CadError) -> tuple[str, str]:
    """Map a :class:`CadError` to a stable code and a message safe to return.

    The taxonomy in :mod:`app.domains.cad.errors` deliberately keeps its
    exceptions minimal -- no common ``code`` attribute -- because the right response
    to each differs. The mapping therefore lives here, next to the thing that
    persists it, rather than being bolted onto every exception.

    The message is written here rather than taken from ``str(exc)`` on purpose. A
    provider's own diagnostics and a dependency's path both tend to contain the
    scratch directory the job ran in, and that ends up in a database column and
    then in an API response. The full text goes to the log, where it is useful and
    not public.
    """
    if isinstance(exc, CadDependencyMissingError):
        return "CAD_DEPENDENCY_MISSING", f"CAD dependency unavailable: {exc.component}"
    if isinstance(exc, GeometryEngineUnavailableError):
        return "CAD_ENGINE_UNAVAILABLE", "The configured geometry engine is unavailable"
    if isinstance(exc, CadJobTimeoutError):
        return (
            "CAD_JOB_TIMEOUT",
            f"The {exc.provider} worker exceeded its {exc.timeout_seconds:g}s time budget and was terminated",
        )
    if isinstance(exc, CadProviderError):
        return "CAD_PROVIDER_ERROR", f"The {exc.provider} provider reported a failure"
    if isinstance(exc, CadSecurityError):
        return "CAD_REQUEST_REJECTED", "The job request was rejected for safety reasons"
    if isinstance(exc, CadJobError):
        return "CAD_INVALID_RESULT", "The worker returned a result the API could not accept"
    if isinstance(exc, CadStorageError):
        # Worth its own code: this is almost always the disk, and "the CAD job
        # failed" would send an operator looking at the geometry code.
        return "CAD_STORAGE_ERROR", "The generated artifact could not be written to storage"
    return "CAD_ERROR", "The CAD job failed"


class CadRequestRejected(Exception):
    """The request is not runnable and no worker was invoked.

    Distinct from a :class:`~app.domains.cad.errors.CadError` on purpose: those
    describe a job that ran, and are recorded. This one describes a request that
    never became a job, so there is nothing to record and the caller should be
    told the request was wrong.
    """

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class CadJobOutcome:
    """The terminal state of one CAD job, whether or not it produced geometry.

    ``run`` is ``None`` only when the toolchain was unavailable: the job was never
    invoked, so there is no invocation to describe. Every other outcome, including
    a failure, has a row.
    """

    run: CadJobRun | None
    artifacts: list[CadArtifact]
    geometry_artifact_id: str | None
    validation_run_id: str | None
    stale: bool
    error_code: str | None = None
    error_message: str | None = None
    #: Set when the toolchain itself is unavailable, so no run was recorded.
    unavailable: bool = False


#: Which ``CadJobOptions`` flag governs which artifact kind. A caller can narrow the
#: requested outputs, never widen them past what the deployment enables.
_OUTPUT_FLAGS: dict[str, str] = {
    "glb": "write_glb",
    "step": "write_step",
    "ifc": "write_ifc",
    "freecad_document": "write_fcstd",
}


def _element_from_alternative(alternative: DesignAlternative) -> MassingElement:
    """Derive the one solid the kernel should build for *alternative*.

    Raises :class:`CadRequestRejected` rather than letting pydantic surface a
    validation error: a parameter set the design engine wrote should not be
    possible, and if it is, the failure has to say *which* parameter is unusable.
    """
    params: dict[str, Any] = alternative.design_parameters_json or {}

    def number(key: str) -> float:
        value = params.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise CadRequestRejected(
                "CAD_PARAMETERS_INCOMPLETE",
                f"Design alternative {alternative.id} has no usable '{key}'",
                status=409,
            )
        return float(value)

    width = number("footprint_width_m")
    depth = number("footprint_depth_m")
    floor_height = number("floor_to_floor_height_m")
    floors = params.get("floor_count")
    if not isinstance(floors, int) or isinstance(floors, bool) or floors < 1:
        raise CadRequestRejected(
            "CAD_PARAMETERS_INCOMPLETE",
            f"Design alternative {alternative.id} has no usable 'floor_count'",
            status=409,
        )

    if width <= 0 or depth <= 0:
        raise CadRequestRejected(
            "CAD_PARAMETERS_INVALID",
            f"Design alternative {alternative.id} has a non-positive footprint",
            status=409,
        )

    height = floors * floor_height
    if height <= 0:
        raise CadRequestRejected(
            "CAD_PARAMETERS_INVALID",
            f"Design alternative {alternative.id} resolves to a non-positive height",
            status=409,
        )
    # The protocol caps a single mass at 1000 m. Report that as a property of the
    # alternative rather than as a pydantic error from deep inside the stack.
    if height > 1000.0:
        raise CadRequestRejected(
            "CAD_PARAMETERS_INVALID",
            f"Design alternative {alternative.id} resolves to {height:.1f} m, above the 1000 m single-mass limit",
            status=409,
        )

    return MassingElement(
        id=f"{alternative.id}-mass",
        kind="building_mass",
        name=alternative.name or "Building mass",
        footprint=Footprint(
            points=[(0.0, 0.0), (width, 0.0), (width, depth), (0.0, depth)]
        ),
        base_elevation_m=0.0,
        height_m=height,
        material_class="conceptual_mass",
        # Traceable back to the design decision rather than to the client.
        source_reference=f"design_alternative:{alternative.id}",
    )


def build_request(
    *,
    alternative: DesignAlternative,
    project: Project,
    config: CadConfig,
    requested_outputs: list[str] | None,
    job_id: str,
) -> CadJobRequest:
    """Assemble the worker request. The client contributes no geometry."""
    options = CadJobOptions(
        write_glb=config.write_glb,
        write_step=config.write_step,
        write_ifc=config.write_ifc,
        write_fcstd=config.write_fcstd,
        ifc_schema=config.ifc_schema,
    )

    if requested_outputs:
        unknown = sorted(set(requested_outputs) - set(ARTIFACT_EXTENSIONS))
        if unknown:
            raise CadRequestRejected(
                "CAD_UNKNOWN_OUTPUT",
                f"Unknown requested output(s): {', '.join(unknown)}",
                status=400,
            )
        # Narrowing only. A caller cannot switch on an output this deployment has
        # turned off, which keeps the toggle a deployment decision.
        for kind, flag in _OUTPUT_FLAGS.items():
            if kind not in requested_outputs:
                setattr(options, flag, False)
        enabled = [k for k, f in _OUTPUT_FLAGS.items() if getattr(options, f)]
        if not enabled:
            raise CadRequestRejected(
                "CAD_NO_OUTPUTS_ENABLED",
                "None of the requested outputs are enabled on this deployment",
                status=409,
            )

    return CadJobRequest(
        job_id=job_id,
        alternative_ref=alternative.id,
        project_name=project.name or "AIrchitect Project",
        elements=[_element_from_alternative(alternative)],
        options=options,
        mesh_deflection_m=config.mesh_deflection_m,
        mesh_angular_deflection_rad=config.mesh_angular_deflection_rad,
        freecad_timeout_seconds=config.freecad_timeout_seconds,
    )


def _run_worker_blocking(
    request: CadJobRequest,
    config: CadConfig,
    capabilities: WorkerCapabilities | None,
    organization_id: str,
) -> tuple[CadJobResult, dict[str, StoredBlob]]:
    """The blocking half of a job: execute the worker, then put the bytes away.

    Split out because both steps block for as long as the job takes -- the worker
    is a subprocess and the artifacts are base64 in memory -- and neither may run
    on the event loop.

    ``organization_id`` is passed in rather than read off the request because the
    store keys on organisation and must be told the owner rather than trusting a
    value that travelled with the payload.
    """
    result = run_cad_job(request, config, capabilities=capabilities)
    store = ContentAddressedStore(config.artifact_root_path())
    stored = store_worker_artifacts(store, organization_id=organization_id, result=result)
    return result, stored


async def run_cad_job_for_alternative(
    session: AsyncSession,
    *,
    project: Project,
    version: ProjectVersion,
    alternative: DesignAlternative,
    actor_id: str,
    config: CadConfig,
    requested_outputs: list[str] | None = None,
    capabilities: WorkerCapabilities | None = None,
    world: WorldModelRevision | None = None,
) -> CadJobOutcome:
    """Generate real geometry for *alternative* and record the outcome.

    The blocking work is dispatched to a worker thread, so a slow or hung CAD
    kernel cannot stall the event loop for every other request in the process.
    """
    from starlette.concurrency import run_in_threadpool

    if world is None:
        world = await resolve_current_world(session, version)

    # Unique per invocation, not per alternative. This is a correlation id for the
    # worker's own logs and for the run row, and an alternative may legitimately be
    # generated many times over. Callers poll the run's own id, not this.
    job_id = f"cad-{alternative.id[:8]}-{uuid4().hex[:12]}"
    request = build_request(
        alternative=alternative,
        project=project,
        config=config,
        requested_outputs=requested_outputs,
        job_id=job_id,
    )

    started = time.monotonic()
    try:
        result, stored = await run_in_threadpool(
            _run_worker_blocking,
            request,
            config,
            capabilities,
            project.organization_id,
        )
    except CadDependencyMissingError as exc:
        # Nothing was invoked, so there is no run to record. This is a deployment
        # problem, not a job outcome, and the caller needs to be able to tell them
        # apart: retrying will not help until the toolchain is installed.
        code, message = classify_failure(exc)
        logger.error("cad_toolchain_unavailable", extra={"error": str(exc)})
        return CadJobOutcome(
            run=None,
            artifacts=[],
            geometry_artifact_id=None,
            validation_run_id=None,
            stale=False,
            error_code=code,
            error_message=message,
            unavailable=True,
        )
    except CadError as exc:
        # A failure after the worker was invoked is an outcome, not a transport
        # error, so it gets a row: the run is evidence of what was attempted and
        # why it did not produce geometry.
        code, message = classify_failure(exc)
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.warning(
            "cad_job_failed",
            extra={"job_id": job_id, "error_code": code, "error": str(exc)},
        )
        run = await record_cad_failure(
            session,
            project=project,
            version=version,
            world=world,
            actor_id=actor_id,
            provider=config.provider,
            request=request,
            error_code=code,
            error_message=message,
            capabilities=capabilities,
            duration_ms=duration_ms,
        )
        await session.commit()
        return CadJobOutcome(
            run=run,
            artifacts=[],
            geometry_artifact_id=None,
            validation_run_id=None,
            stale=False,
            error_code=code,
            error_message=message,
        )

    duration_ms = int((time.monotonic() - started) * 1000)
    recorded: RecordedCadRun = await record_cad_success(
        session,
        project=project,
        version=version,
        world=world,
        actor_id=actor_id,
        provider=result.provider.provider or config.provider,
        request=request,
        result=result,
        stored=stored,
        alternative_id=alternative.id,
        design_hash=alternative.design_hash or "",
        capabilities=capabilities,
        duration_ms=duration_ms,
    )
    await session.commit()
    return CadJobOutcome(
        run=recorded.run,
        artifacts=recorded.artifacts,
        geometry_artifact_id=recorded.geometry_artifact_id,
        validation_run_id=recorded.validation_run_id,
        stale=recorded.stale,
    )
