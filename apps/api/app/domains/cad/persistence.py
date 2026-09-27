"""Persisting Phase 18 CAD/BIM results.

This module is the boundary between "the worker produced something" and "the
project has a durable, auditable record of it". It is deliberately separate from
the runner: the runner decides whether a job may run and hands back bytes, while
everything here is about what the database knows afterwards.

Four rules shape the code.

**Failures are recorded, not discarded.** A geometry pipeline that cannot explain
why a model it did not produce was rejected cannot be debugged, so a rejected,
timed-out, or crashed run still gets a ``cad_job_runs`` row. Only a run that
produced nothing has nothing to record.

**The revision binding is verified at write time, not assumed.** A worker run takes
real time, and the world model can gain a revision while it is in flight. Recording
the result as current would be a lie, so the repository re-resolves the current
revision at write time and downgrades the geometry to ``STALE`` when the hash no
longer matches. This is the same invariant the design engine enforces when it
invalidates alternatives.

**The bytes stay out of the database.** Artifacts are decoded, verified, and handed
to the content-addressed store; the row keeps only metadata and a ``storage_key``.

**Identical geometry is not stored twice.** ``geometry_artifacts`` and
``validation_runs`` are unique on their content hash within a project version. A
re-run that produces the same measurements therefore points at the existing
geometry rather than attempting a second row that would violate the constraint.
"""

from __future__ import annotations

import base64
import binascii
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ArtifactVersion,
    CadArtifact,
    CadJobRun,
    DesignAlternative,
    EvidenceRecord,
    GeometryArtifact,
    Project,
    ProjectVersion,
    ValidationCheck,
    ValidationRun,
    WorldModelRevision,
)
from app.domains.cad.capability import WorkerCapabilities
from app.domains.cad.errors import CadJobError
from app.domains.cad.protocol import (
    ARTIFACT_CONTENT_TYPES,
    ArtifactRef,
    CadJobRequest,
    CadJobResult,
    CadValidationResult,
    ProviderInfo,
)
from app.domains.cad.storage import ContentAddressedStore, StoredBlob, sha256_bytes
from app.domains.foundation.service import audit
from app.domains.lifecycle.service import canonical_hash, new_artifact

logger = logging.getLogger(__name__)

#: Request fields that describe *this attempt* rather than the geometry produced.
#: They are excluded from the request hash so that regenerating identical geometry
#: with a different timeout, scratch directory, or job label hashes the same.
#: Mesh deflection is deliberately *not* excluded: it changes the GLB.
VOLATILE_REQUEST_FIELDS: frozenset[str] = frozenset(
    {"output_dir", "sandbox_root", "freecad_timeout_seconds", "job_id"}
)

#: Validation check statuses the worker emits, mapped to a severity for the database.
#: Anything unrecognised is treated as informational rather than as an error, because
#: inventing an ERROR for an unknown status would block a run that actually passed.
_SEVERITY_BY_STATUS: dict[str, str] = {
    "FAIL": "ERROR",
    "FAILED": "ERROR",
    "ERROR": "ERROR",
    "WARN": "WARNING",
    "WARNING": "WARNING",
}


class CadRevisionError(CadJobError):
    """No world model revision exists to bind geometry to."""


@dataclass(slots=True)
class RecordedCadRun:
    """What a persist call wrote, for the caller to return to an API."""

    run: CadJobRun
    artifacts: list[CadArtifact] = field(default_factory=list)
    geometry_artifact_id: str | None = None
    validation_run_id: str | None = None
    #: True when the world model moved while the worker was running, so the geometry
    #: was recorded as STALE instead of CURRENT.
    stale: bool = False


async def resolve_current_world(
    session: AsyncSession, version: ProjectVersion
) -> WorldModelRevision:
    """Return the highest revision for a project version.

    Geometry is meaningless without a revision to attribute it to, so this raises
    rather than returning None: an unbound geometry artifact would be a row that no
    consumer can trust or later invalidate.
    """
    world = await session.scalar(
        select(WorldModelRevision)
        .where(WorldModelRevision.project_version_id == version.id)
        .order_by(WorldModelRevision.revision.desc())
    )
    if world is None:
        raise CadRevisionError(
            f"project version {version.id} has no world model revision to bind geometry to"
        )
    return world


def request_hash(request: CadJobRequest) -> str:
    """Hash the semantically meaningful part of a request."""
    payload = request.model_dump(mode="json")
    for name in VOLATILE_REQUEST_FIELDS:
        payload.pop(name, None)
    return canonical_hash(payload)


def _version_fields(
    provider: str,
    reported: ProviderInfo | None = None,
    capabilities: WorkerCapabilities | None = None,
) -> dict[str, str | None]:
    """Resolve the toolchain versions recorded against a run.

    ``reported`` is the provider block the worker returned with *this* result, and it
    wins when present: it is a fact about the run rather than a probe taken earlier.
    The capability snapshot is the fallback, and is all a failed run has, since a run
    that produced no result never reported a provider.

    Both are kept because a toolchain upgrade between two otherwise identical runs is
    exactly the kind of change that explains a difference in the output.
    """
    if reported is not None:
        return {
            "provider_engine_name": reported.engine_name or "",
            "provider_engine_version": reported.engine_version or "",
            "occt_version": reported.occt_version or "",
            "ifc_library_version": reported.ifc_library_version or "",
            "freecad_version": reported.freecad_version or None,
        }
    if capabilities is None:
        return {
            "provider_engine_name": "",
            "provider_engine_version": "",
            "occt_version": "",
            "ifc_library_version": "",
            "freecad_version": None,
        }
    if provider == "freecad":
        return {
            "provider_engine_name": "FreeCAD",
            "provider_engine_version": capabilities.freecad.version or "",
            # FreeCAD bundles its own OCCT, so report the one it actually used.
            "occt_version": (
                capabilities.freecad.occt_version or capabilities.occt.occt_version or ""
            ),
            "ifc_library_version": capabilities.ifc.version or "",
            "freecad_version": capabilities.freecad.version or None,
        }
    return {
        "provider_engine_name": capabilities.occt.engine_name or "",
        "provider_engine_version": capabilities.occt.engine_version or "",
        "occt_version": capabilities.occt.occt_version or "",
        "ifc_library_version": capabilities.ifc.version or "",
        "freecad_version": capabilities.freecad.version or None,
    }


def _toolchain_provenance(
    reported: ProviderInfo | None, capabilities: WorkerCapabilities | None
) -> dict[str, object]:
    """The complete toolchain record for a run.

    The scalar columns on ``cad_job_runs`` hold the versions worth querying on; this
    keeps everything the worker reported, including the interpreter build and the
    toolchain digest, so a run can be reproduced or explained later.
    """
    provenance: dict[str, object] = {}
    if capabilities is not None:
        provenance["capability_snapshot"] = capabilities.model_dump(mode="json")
    if reported is not None:
        provenance["provider"] = reported.model_dump(mode="json")
    return provenance


def _engine_version(
    provider: str,
    reported: ProviderInfo | None = None,
    capabilities: WorkerCapabilities | None = None,
) -> str:
    fields = _version_fields(provider, reported, capabilities)
    return fields["provider_engine_version"] or "unknown"


async def _revision_is_still_current(
    session: AsyncSession, version: ProjectVersion, world: WorldModelRevision
) -> bool:
    """Check whether the revision a run was bound to is still the current one.

    Re-resolved at write time. Between a run starting and finishing the world model
    may have gained a revision, and a result computed from the old one must not be
    published as current.
    """
    current = await resolve_current_world(session, version)
    if current.id != world.id:
        return False
    return (current.model_hash or "") == (world.model_hash or "")


def _decode_artifact(ref: ArtifactRef) -> bytes:
    """Decode and verify one base64 artifact.

    The runner already checks these, but this is the point of no return: the bytes
    are about to become a durable file. Verifying again means a bug in the runner, or
    a hand-edited response file, cannot poison the artifact store.
    """
    try:
        data = base64.b64decode(ref.payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CadJobError(
            f"artifact {ref.filename!r} payload is not valid base64: {exc}"
        ) from exc
    if len(data) != ref.byte_size:
        raise CadJobError(
            f"artifact {ref.filename!r} is {len(data)} bytes but declared {ref.byte_size}"
        )
    digest = sha256_bytes(data)
    if digest != ref.sha256:
        raise CadJobError(
            f"artifact {ref.filename!r} hashes to {digest} but declared {ref.sha256}"
        )
    return data


def store_worker_artifacts(
    store: ContentAddressedStore, *, organization_id: str, result: CadJobResult
) -> dict[str, StoredBlob]:
    """Decode every artifact in a result and write it to the store.

    Everything is decoded and verified before anything is written, so a malformed
    artifact cannot leave a half-populated set of files behind.
    """
    decoded = [(ref, _decode_artifact(ref)) for ref in result.artifacts]
    stored: dict[str, StoredBlob] = {}
    for ref, data in decoded:
        expected = ARTIFACT_CONTENT_TYPES.get(ref.kind)
        if expected is not None and ref.content_type != expected:
            # The worker's value is what gets stored -- it produced the file -- but a
            # mismatch means the two sides disagree, and the parity test should have
            # caught it. Failing here turns a silent mislabelled download into a bug
            # that is impossible to miss.
            raise CadJobError(
                f"artifact {ref.filename!r} declares content type "
                f"{ref.content_type!r} but the protocol expects {expected!r}"
            )
        blob = store.put_bytes(
            data, organization_id=organization_id, kind=ref.kind, content_type=ref.content_type
        )
        stored[ref.kind] = blob
    return stored


def _validation_status(validation: CadValidationResult | None) -> str:
    """Map the worker's validation outcome onto a validation-run status.

    ``None`` means the worker skipped validation (``run_validation: false``). The
    database's BLOCKED means "not established", which is exactly right: geometry was
    produced but nothing vouched for it, so downstream consumers must not treat it as
    validated.
    """
    if validation is None:
        return "BLOCKED"
    return "PASSED" if validation.valid else "FAILED"


async def record_cad_failure(
    session: AsyncSession,
    *,
    project: Project,
    version: ProjectVersion,
    world: WorldModelRevision,
    actor_id: str,
    provider: str,
    request: CadJobRequest,
    error_code: str,
    error_message: str,
    capabilities: WorkerCapabilities | None = None,
    duration_ms: int | None = None,
) -> CadJobRun:
    """Record a run that produced no geometry.

    ``error_code`` comes from the typed error taxonomy, which is why it is safe to
    persist. ``error_message`` is operator-facing and may name filesystem paths, so
    it must be filtered before it reaches a client -- but it is worth keeping here.
    """
    run = CadJobRun(
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        world_model_revision_id=world.id,
        input_world_model_hash=world.model_hash or "",
        job_id=request.job_id,
        provider=provider,
        request_hash=request_hash(request),
        element_count=len(request.elements),
        # A failed run never reported a provider, so the snapshot is all there is.
        capabilities_json=_toolchain_provenance(None, capabilities),
        status="FAILED",
        error_code=error_code,
        error_message=error_message,
        requested_by=actor_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
        **_version_fields(provider, None, capabilities),
    )
    session.add(run)
    await session.flush()
    logger.info(
        "cad_job_failed",
        extra={
            "cad_job_run_id": run.id,
            "provider": provider,
            "error_code": error_code,
            "project_version_id": version.id,
        },
    )
    return run


async def record_cad_success(
    session: AsyncSession,
    *,
    project: Project,
    version: ProjectVersion,
    world: WorldModelRevision,
    actor_id: str,
    provider: str,
    request: CadJobRequest,
    result: CadJobResult,
    stored: dict[str, StoredBlob],
    alternative_id: str | None = None,
    design_hash: str = "",
    capabilities: WorkerCapabilities | None = None,
    duration_ms: int | None = None,
) -> RecordedCadRun:
    """Record a successful run and everything it produced.

    Writes, in order: the run; an ``ArtifactVersion`` and ``CadArtifact`` per binary;
    the ``GeometryArtifact`` bound to the world model revision; and a
    ``ValidationRun`` with its checks.

    Each binary gets an ``ArtifactVersion`` because the rest of AIrchitect already
    reasons about artifacts through that table, and the existing dependency graph
    and staleness cascade then work unchanged. The ``CadArtifact`` row alongside it
    records where the bytes live, which ``ArtifactVersion`` deliberately does not.
    """
    # Resolve the alternative before writing anything. A foreign-key violation would
    # otherwise surface at flush time with artifacts already stored, leaving a
    # half-populated record of a run that cannot be attributed to an alternative.
    if alternative_id is not None:
        await _assert_alternative_exists(session, alternative_id)

    stale = not await _revision_is_still_current(session, version, world)
    status = "STALE" if stale else "CURRENT"
    run_hash = request_hash(request)
    reported = result.provider
    engine_version = _engine_version(provider, reported, capabilities)
    measurements = [m.model_dump(mode="json") for m in result.measurements]
    validation_document = result.validation.model_dump(mode="json") if result.validation else None

    run = CadJobRun(
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        world_model_revision_id=world.id,
        input_world_model_hash=world.model_hash or "",
        design_alternative_id=alternative_id,
        job_id=request.job_id or result.job_id,
        provider=provider,
        request_hash=run_hash,
        element_count=result.element_count or len(request.elements),
        capabilities_json=_toolchain_provenance(reported, capabilities),
        status="SUCCEEDED",
        measurements_json={
            "combined_volume_m3": result.combined_volume_m3,
            "combined_area_m2": result.combined_area_m2,
            "combined_bounding_box": (
                result.combined_bounding_box.model_dump(mode="json")
                if result.combined_bounding_box
                else None
            ),
            "elements": measurements,
        },
        validation_json=validation_document or {},
        warnings_json=list(result.warnings),
        requested_by=actor_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
        **_version_fields(provider, reported, capabilities),
    )
    session.add(run)
    await session.flush()

    artifact_rows: list[CadArtifact] = []
    artifact_versions: list[ArtifactVersion] = []
    for kind, blob in sorted(stored.items()):
        artifact_version = await new_artifact(
            session,
            project=project,
            version=version,
            world=world,
            actor=actor_id,
            artifact_type=f"cad_{kind}",
            # Metadata only. The payload is deliberately absent: a STEP or GLB does
            # not belong in a JSON column that is loaded on every read of the row.
            payload={
                "kind": kind,
                "filename": blob.filename,
                "content_type": blob.content_type,
                "byte_size": blob.byte_size,
                "sha256": blob.sha256,
                "storage_key": blob.storage_key,
                "media_role": blob.media_role,
                "cad_job_run_id": run.id,
            },
            alternative_id=alternative_id,
            status=status,
        )
        artifact_version.output_hash = blob.sha256
        artifact_version.provenance_json = {
            **artifact_version.provenance_json,
            "cad_job_run_id": run.id,
            "provider": provider,
            "world_model_revision_id": world.id,
            "world_model_hash": world.model_hash,
            "world_model_is_current": not stale,
        }
        row = CadArtifact(
            cad_job_run_id=run.id,
            artifact_version_id=artifact_version.id,
            organization_id=project.organization_id,
            project_id=project.id,
            project_version_id=version.id,
            kind=kind,
            filename=blob.filename,
            content_type=blob.content_type or "application/octet-stream",
            byte_size=blob.byte_size,
            sha256=blob.sha256,
            storage_key=blob.storage_key,
            media_role=blob.media_role,
        )
        session.add(row)
        artifact_rows.append(row)
        artifact_versions.append(artifact_version)
    await session.flush()

    geometry_id: str | None = None
    geometry_version: ArtifactVersion | None = None
    # Geometry is recorded when the worker actually produced solids, not merely
    # because the run succeeded. A result that reports no elements produced no
    # geometry, and inventing a GeometryArtifact for it would give consumers a
    # measurement of nothing.
    produced_geometry = result.element_count > 0 and result.combined_volume_m3 is not None
    if produced_geometry and alternative_id:
        geometry_hash = canonical_hash(
            {
                "request_hash": run_hash,
                "provider": provider,
                "engine_version": engine_version,
                "measurements": measurements,
            }
        )
        existing = await session.scalar(
            select(GeometryArtifact).where(
                GeometryArtifact.project_version_id == version.id,
                GeometryArtifact.geometry_hash == geometry_hash,
            )
        )
        if existing is not None:
            # Identical geometry from an earlier run. Reuse it instead of writing a
            # second row that the uniqueness constraint would reject; the new run
            # still points at it, so the provenance chain stays intact.
            geometry_id = existing.id
        else:
            geometry_version = await new_artifact(
                session,
                project=project,
                version=version,
                world=world,
                actor=actor_id,
                artifact_type="cad_geometry",
                payload={
                    "cad_job_run_id": run.id,
                    "measurements": measurements,
                    "combined_volume_m3": result.combined_volume_m3,
                    "combined_area_m2": result.combined_area_m2,
                    "stale": stale,
                },
                # The geometry is derived from the exported binaries, so the
                # dependency edges are recorded rather than implied.
                dependencies=artifact_versions or None,
                alternative_id=alternative_id,
                status=status,
            )
            geometry_version.output_hash = geometry_hash
            geometry = GeometryArtifact(
                artifact_version_id=geometry_version.id,
                project_id=project.id,
                project_version_id=version.id,
                alternative_id=alternative_id,
                world_model_revision_id=world.id,
                geometry_hash=geometry_hash,
                input_world_model_hash=world.model_hash or "",
                design_hash=design_hash,
                engine_name=provider,
                engine_version=engine_version,
                status=status,
                provenance_json={
                    "cad_job_run_id": run.id,
                    "world_model_revision_id": world.id,
                    "world_model_hash": world.model_hash,
                    "world_model_is_current": not stale,
                    "design_alternative_id": alternative_id,
                    "design_hash": design_hash,
                    "provider": provider,
                },
                payload_json={
                    "measurements": measurements,
                    "combined_volume_m3": result.combined_volume_m3,
                    "combined_area_m2": result.combined_area_m2,
                    "combined_bounding_box": (
                        result.combined_bounding_box.model_dump(mode="json")
                        if result.combined_bounding_box
                        else None
                    ),
                },
            )
            session.add(geometry)
            await session.flush()
            geometry_id = geometry.id
    run.geometry_artifact_id = geometry_id

    validation_id: str | None = None
    validation = result.validation
    if validation is not None:
        validation_hash = canonical_hash(
            {"request_hash": run_hash, "provider": provider, "validation": validation_document}
        )
        existing_validation = await session.scalar(
            select(ValidationRun).where(
                ValidationRun.project_version_id == version.id,
                ValidationRun.validation_hash == validation_hash,
            )
        )
        if existing_validation is not None:
            validation_id = existing_validation.id
        else:
            validation_version = await new_artifact(
                session,
                project=project,
                version=version,
                world=world,
                actor=actor_id,
                artifact_type="cad_validation",
                payload={"cad_job_run_id": run.id, "validation": validation_document},
                # The validation judges the geometry, so that is what it depends on.
                dependencies=[geometry_version] if geometry_version else None,
                alternative_id=alternative_id,
                status=status,
            )
            validation_version.output_hash = validation_hash
            validation_run = ValidationRun(
                artifact_version_id=validation_version.id,
                project_id=project.id,
                project_version_id=version.id,
                world_model_revision_id=world.id,
                design_alternative_id=alternative_id,
                input_hashes_json={
                    "request_hash": run_hash,
                    "world_model_hash": world.model_hash,
                },
                engine_name=provider,
                engine_version=engine_version,
                # The protocol schema version identifies the check set that ran. The
                # tolerances it was given are in the run payload.
                config_version=request.schema_version,
                validation_hash=validation_hash,
                status=_validation_status(validation),
                provenance_json={
                    "cad_job_run_id": run.id,
                    "world_model_is_current": not stale,
                },
                payload_json={"validation": validation_document},
            )
            session.add(validation_run)
            await session.flush()
            validation_id = validation_run.id

            for check in validation.checks:
                session.add(
                    ValidationCheck(
                        validation_run_id=validation_run.id,
                        code=check.code,
                        severity=_SEVERITY_BY_STATUS.get(check.status.upper(), "INFO"),
                        category="GEOMETRY",
                        status=check.status,
                        # The database's message column is the only free text here, so
                        # the worker's structured fields (expected/actual/source) are
                        # left in the run payload rather than flattened into it.
                        message=check.detail or check.code,
                        source_artifact_id=geometry_id,
                    )
                )
            await session.flush()

    # Evidence for the binary the viewer loads, so a served GLB is traceable to the
    # exact bytes and the toolchain that produced them.
    viewer_row = next((row for row in artifact_rows if row.kind == "glb"), None)
    if viewer_row is not None:
        session.add(
            EvidenceRecord(
                artifact_version_id=viewer_row.artifact_version_id,
                project_version_id=version.id,
                source_type="cad_artifact",
                source_uri=viewer_row.storage_key,
                source_hash=viewer_row.sha256,
                source_version=viewer_row.content_type,
                content_hash=viewer_row.sha256,
                verification_method="sha256_content_address",
                verified_by=actor_id,
                verification_status="verified",
            )
        )

    if stale:
        logger.warning(
            "cad_geometry_recorded_stale",
            extra={
                "cad_job_run_id": run.id,
                "project_version_id": version.id,
                "reason": "world_model_revision_changed_during_generation",
            },
        )

    await audit(
        session,
        project=project,
        version=version,
        actor=actor_id,
        action="CAD_GEOMETRY_INVALIDATED" if stale else "CAD_GEOMETRY_RECORDED",
        entity="cad_job_run",
        entity_id=run.id,
        metadata={
            "provider": provider,
            "artifact_kinds": sorted(stored),
            "world_model_revision_id": world.id,
            "world_model_hash": world.model_hash,
            "stale": stale,
        },
    )
    logger.info(
        "cad_geometry_recorded",
        extra={
            "cad_job_run_id": run.id,
            "provider": provider,
            "artifact_count": len(artifact_rows),
            "stale": stale,
            "project_version_id": version.id,
        },
    )
    return RecordedCadRun(
        run=run,
        artifacts=artifact_rows,
        geometry_artifact_id=geometry_id,
        validation_run_id=validation_id,
        stale=stale,
    )


async def _assert_alternative_exists(
    session: AsyncSession, alternative_id: str
) -> DesignAlternative:
    """Confirm the alternative exists before binding geometry to it.

    The foreign key would catch this anyway, but the error would surface at flush
    time after the artifacts were already written, leaving a partial record. Checking
    first means the run either records completely or not at all.
    """
    alternative = await session.get(DesignAlternative, alternative_id)
    if alternative is None:
        raise CadJobError(f"design alternative {alternative_id} does not exist")
    return alternative
