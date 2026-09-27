"""HTTP surface for the CAD/BIM pipeline.

Four endpoints: generate geometry for an alternative, read a run, list a run's
artifacts, download one artifact.

Scoping and non-disclosure
--------------------------

Every path is nested under project and version, and every handler resolves that
pair through :func:`resolve_project_version` before touching anything else. That
function is what makes a cross-tenant request a 404 with no detail: a project
that belongs to another organisation and a project that does not exist produce
the same response, because telling them apart is itself a leak.

The download endpoint goes further. It confirms the artifact belongs to the
resolved project *and* version, so an artifact id from another project is
indistinguishable from a wrong one. A row whose bytes have been pruned from the
store raises :class:`CadArtifactMissingError`, which maps to the same 404 -- a
caller cannot learn that an artifact id is real but its content is gone.

This is why ``storage_key`` is a relative, opaque string in responses: it is
meaningful only to the download endpoint, and never a path on the server.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadArtifact, CadJobRun, DesignAlternative, Project, ProjectVersion, User, WorldModelRevision
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.cad.capability import probe_capabilities
from app.domains.cad.config import CadConfig
from app.domains.cad.errors import CadArtifactMissingError, CadError, CadStorageError
from app.domains.cad.orchestrator import CadRequestRejected, classify_failure, run_cad_job_for_alternative
from app.domains.cad.storage import ContentAddressedStore
from app.domains.foundation.service import error, resolve_project_version, resolve_world_model
from .schemas import CadGenerationRequest, artifact_out, job_out

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cad-bim"])


async def _load_run(
    session: AsyncSession, project: Project, version: ProjectVersion, run_id: str
) -> tuple[CadJobRun, WorldModelRevision]:
    """Resolve a run inside an already-authorised project and version.

    The project/version predicates are repeated here even though the caller has
    already been authorised, because a run id alone is a global identifier: without
    them a valid id from another project would resolve.
    """
    run = await session.scalar(
        select(CadJobRun).where(
            CadJobRun.id == run_id,
            CadJobRun.project_id == project.id,
            CadJobRun.project_version_id == version.id,
        )
    )
    if run is None:
        raise error(404, "CAD_JOB_NOT_FOUND", "CAD job not found")
    world = await resolve_world_model(session, version.id)
    return run, world


@router.post(
    "/projects/{project_id}/versions/{version_ref}/design/alternatives/{alternative_id}/cad",
    status_code=201,
)
async def generate_cad(
    project_id: str,
    version_ref: str,
    alternative_id: str,
    body: CadGenerationRequest | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate real geometry for a design alternative.

    The request blocks until the worker reaches a terminal state. The worker runs
    in a worker thread, so a slow kernel delays this request only -- not the whole
    process -- and the runner's wall-clock timeout bounds how long that can be.

    Returns 201 for a run that completed *or* one that failed after being invoked;
    a failure is a recorded outcome, not a transport error, so the response carries
    the run id, the error code, and the fact that nothing was produced. A 503 is
    reserved for the toolchain being absent, which is a deployment fault and which
    deliberately records no run, because no job was ever invoked.
    """
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    if version.status != "COMMITTED":
        # NB: the context key is ``version_status`` and not ``status``: ``error``'s
        # own first parameter is called ``status``, so passing ``status=`` here
        # would be a duplicate argument and raise a TypeError.
        raise error(
            409,
            "WORLD_MODEL_INVALID",
            "Commit the canonical project version before CAD generation",
            version_status=version.status,
        )
    alternative = await session.scalar(
        select(DesignAlternative).where(
            DesignAlternative.id == alternative_id,
            DesignAlternative.project_id == project.id,
            DesignAlternative.project_version_id == version.id,
        )
    )
    if alternative is None:
        raise error(404, "ALTERNATIVE_NOT_FOUND", "Design alternative not found")

    world = await resolve_world_model(session, version.id)
    if alternative.status == "STALE" or alternative.input_world_model_hash != world.model_hash:
        raise error(
            409,
            "STALE_ARTIFACT",
            "A stale alternative cannot be sent to CAD; regenerate from the current World Model",
        )

    config = CadConfig.from_settings()
    if config.geometry_engine != "cad_bim":
        raise error(
            409,
            "CAD_ENGINE_DISABLED",
            "CAD geometry generation is disabled on this deployment",
            geometry_engine=config.geometry_engine,
        )
    try:
        capabilities = probe_capabilities(config)
    except CadError as exc:
        # Probed before any job is recorded so an absent toolchain is reported as
        # the deployment fault it is, rather than as a failed CAD run.
        code, message = classify_failure(exc)
        logger.error("cad_toolchain_unavailable", extra={"error": str(exc)})
        raise error(503, code, message) from exc

    try:
        outcome = await run_cad_job_for_alternative(
            session,
            project=project,
            version=version,
            alternative=alternative,
            actor_id=user.id,
            config=config,
            requested_outputs=list(body.requested_outputs) if body and body.requested_outputs else None,
            capabilities=capabilities,
            world=world,
        )
    except CadRequestRejected as exc:
        raise error(exc.status, exc.code, exc.message) from exc

    if outcome.unavailable:
        assert outcome.run is None, "an unavailable toolchain records no run"
        raise error(
            503,
            outcome.error_code or "CAD_UNAVAILABLE",
            outcome.error_message or "The CAD toolchain is not available",
        )

    run = outcome.run
    assert run is not None  # only the unavailable path has no run
    payload = job_out(run, current_hash=world.model_hash or "", stale=outcome.stale)
    return {
        **payload.model_dump(mode="json"),
        "artifacts": [artifact_out(row, version.id).model_dump(mode="json") for row in outcome.artifacts],
        "validation_run_id": outcome.validation_run_id,
    }


@router.get("/projects/{project_id}/versions/{version_ref}/cad/jobs/{run_id}")
async def cad_job_status(
    project_id: str,
    version_ref: str,
    run_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Read a persisted run, including its toolchain and measurements."""
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    run, world = await _load_run(session, project, version, run_id)
    artifacts = list(
        (
            await session.scalars(
                select(CadArtifact).where(CadArtifact.cad_job_run_id == run.id).order_by(CadArtifact.kind)
            )
        ).all()
    )
    return {
        **job_out(run, current_hash=world.model_hash or "").model_dump(mode="json"),
        "artifacts": [artifact_out(row, version.id).model_dump(mode="json") for row in artifacts],
    }


@router.get("/projects/{project_id}/versions/{version_ref}/cad/jobs/{run_id}/artifacts")
async def cad_job_artifacts(
    project_id: str,
    version_ref: str,
    run_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List the binaries a run produced, without their contents."""
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    run, _ = await _load_run(session, project, version, run_id)
    rows = list(
        (
            await session.scalars(
                select(CadArtifact)
                .where(CadArtifact.cad_job_run_id == run.id)
                .order_by(CadArtifact.kind)
            )
        ).all()
    )
    return {
        "cad_job_run_id": run.id,
        "status": run.status,
        "artifacts": [artifact_out(row, version.id).model_dump(mode="json") for row in rows],
    }


@router.get("/projects/{project_id}/versions/{version_ref}/cad/artifacts/{artifact_id}/download")
async def download_cad_artifact(
    project_id: str,
    version_ref: str,
    artifact_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Stream one artifact's bytes.

    A 404 here means one of three indistinguishable things: the artifact does not
    exist, it belongs to another tenant or version, or its content has been pruned
    from the store. All three are 404 with the same body.
    """
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    row = await session.scalar(
        select(CadArtifact).where(
            CadArtifact.id == artifact_id,
            CadArtifact.project_id == project.id,
            CadArtifact.project_version_id == version.id,
        )
    )
    if row is None:
        raise error(404, "CAD_ARTIFACT_NOT_FOUND", "CAD artifact not found")

    store = ContentAddressedStore(CadConfig.from_settings().artifact_root_path())
    try:
        path = store.resolve(row.storage_key)
        if not path.is_file():
            raise CadArtifactMissingError(f"content missing for {row.id}")
    except CadArtifactMissingError:
        # The row exists but its bytes are gone. Same 404 as an unknown id, so a
        # caller cannot enumerate real ids by probing which ones still resolve.
        raise error(404, "CAD_ARTIFACT_NOT_FOUND", "CAD artifact not found") from None
    except CadStorageError:
        # A malformed key is our corruption, not the caller's mistake, so it is
        # reported to them as the same 404 but logged for an operator.
        logger.error(
            "cad_artifact_storage_key_invalid",
            extra={"artifact_id": row.id, "storage_key": row.storage_key},
        )
        raise error(404, "CAD_ARTIFACT_NOT_FOUND", "CAD artifact not found") from None

    return FileResponse(
        path,
        media_type=row.content_type,
        filename=row.filename,
        headers={
            # Lets a client or a proxy cache by content rather than by id, and lets
            # it verify what it received against what the run promised.
            "ETag": f'"{row.sha256}"',
            "X-Cad-Artifact-Sha256": row.sha256,
            "X-Cad-Artifact-Kind": row.kind,
        },
    )
