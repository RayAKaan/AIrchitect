"""Canonical architectural-model to CAD export execution.

This module closes the gap between the persisted canonical model and the existing
bounded CAD worker. Design alternatives remain supported for feasibility workflows,
but the canonical model is the authoritative source for production export: geometry
is projected from the persisted model, executed through the same sandboxed worker,
and recorded through the existing artifact/provenance pipeline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.models import Project, ProjectVersion, WorldModelRevision
from app.domains.cad.capability import WorkerCapabilities
from app.domains.cad.config import CadConfig
from app.domains.cad.errors import CadDependencyMissingError, CadError
from app.domains.cad.model_adapter import build_cad_request
from app.domains.cad.persistence import (
    RecordedCadRun,
    record_cad_failure,
    record_cad_success,
    resolve_current_world,
    store_worker_artifacts,
)
from app.domains.cad.protocol import CadJobOptions, CadJobRequest, CadJobResult
from app.domains.cad.runner import run_cad_job
from app.domains.cad.storage import ContentAddressedStore, StoredBlob
from app.domains.model.schemas import ArchitecturalModel


class CanonicalCadRequestRejected(ValueError):
    """Raised when requested CAD outputs cannot be satisfied by deployment policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class CanonicalCadOutcome:
    run: Any
    artifacts: list[Any]
    geometry_artifact_id: str | None
    validation_run_id: str | None
    stale: bool
    unavailable: bool = False
    error_code: str | None = None
    error_message: str | None = None


def build_canonical_request(
    model: ArchitecturalModel,
    *,
    project_name: str,
    config: CadConfig,
    requested_outputs: list[str] | None = None,
) -> CadJobRequest:
    """Project one canonical model revision into a bounded CAD request.

    The caller may narrow enabled outputs but can never enable a deployment-disabled
    format. The model hash is carried in each projected element's source reference.
    """
    request = build_cad_request(
        model,
        job_id=f"cad-model-{model.revision}-{uuid4().hex[:12]}",
        alternative_ref=f"canonical-model:{model.revision}",
        project_name=project_name,
    )
    options = CadJobOptions(
        write_fcstd=config.write_fcstd,
        write_step=config.write_step,
        write_ifc=config.write_ifc,
        write_glb=config.write_glb,
        run_validation=True,
        ifc_schema=config.ifc_schema,
    )

    if requested_outputs is not None:
        allowed = {"freecad_document", "step", "ifc", "glb"}
        unknown = sorted(set(requested_outputs) - allowed)
        if unknown:
            raise CanonicalCadRequestRejected(
                "CAD_UNKNOWN_OUTPUT", f"Unknown requested output(s): {', '.join(unknown)}"
            )
        for kind, field in {
            "freecad_document": "write_fcstd",
            "step": "write_step",
            "ifc": "write_ifc",
            "glb": "write_glb",
        }.items():
            if kind not in requested_outputs:
                setattr(options, field, False)
        if not any(
            getattr(options, field)
            for field in ("write_fcstd", "write_step", "write_ifc", "write_glb")
        ):
            raise CanonicalCadRequestRejected(
                "CAD_NO_OUTPUTS_ENABLED",
                "None of the requested outputs are enabled on this deployment",
            )

    return request.model_copy(
        update={
            "options": options,
            "mesh_deflection_m": config.mesh_deflection_m,
            "mesh_angular_deflection_rad": config.mesh_angular_deflection_rad,
            "freecad_timeout_seconds": config.freecad_timeout_seconds,
        }
    )


def _run_worker_blocking(
    request: CadJobRequest,
    config: CadConfig,
    capabilities: WorkerCapabilities,
    organization_id: str,
) -> tuple[CadJobResult, dict[str, StoredBlob]]:
    result = run_cad_job(request, config, capabilities=capabilities)
    store = ContentAddressedStore(config.artifact_root_path())
    stored = store_worker_artifacts(
        store, organization_id=organization_id, result=result
    )
    return result, stored


async def run_canonical_cad_export(
    session: AsyncSession,
    *,
    project: Project,
    version: ProjectVersion,
    model: ArchitecturalModel,
    actor_id: str,
    config: CadConfig,
    capabilities: WorkerCapabilities,
    requested_outputs: list[str] | None = None,
    world: WorldModelRevision | None = None,
) -> CanonicalCadOutcome:
    """Execute and durably record a CAD export sourced from the canonical model."""
    if world is None:
        world = await resolve_current_world(session, version)

    request = build_canonical_request(
        model,
        project_name=project.name or "AIrchitect Project",
        config=config,
        requested_outputs=requested_outputs,
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
    except CadDependencyMissingError:
        return CanonicalCadOutcome(
            run=None,
            artifacts=[],
            geometry_artifact_id=None,
            validation_run_id=None,
            stale=False,
            unavailable=True,
            error_code="CAD_DEPENDENCY_MISSING",
            error_message="The configured CAD toolchain is unavailable",
        )
    except CadError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        run = await record_cad_failure(
            session,
            project=project,
            version=version,
            world=world,
            actor_id=actor_id,
            provider=config.provider,
            request=request,
            error_code="CAD_JOB_FAILED",
            error_message="The CAD worker failed while exporting the canonical model",
            capabilities=capabilities,
            duration_ms=duration_ms,
        )
        await session.commit()
        return CanonicalCadOutcome(
            run=run,
            artifacts=[],
            geometry_artifact_id=None,
            validation_run_id=None,
            stale=False,
            error_code="CAD_JOB_FAILED",
            error_message=str(exc),
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
        alternative_id=None,
        design_hash=model.model_dump_json(),
        capabilities=capabilities,
        duration_ms=duration_ms,
    )
    await session.commit()
    return CanonicalCadOutcome(
        run=recorded.run,
        artifacts=recorded.artifacts,
        geometry_artifact_id=recorded.geometry_artifact_id,
        validation_run_id=recorded.validation_run_id,
        stale=recorded.stale,
    )


__all__ = [
    "CanonicalCadOutcome",
    "CanonicalCadRequestRejected",
    "build_canonical_request",
    "run_canonical_cad_export",
]
