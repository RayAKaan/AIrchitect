from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.architectural_model_models import ArchitecturalModelRevision
from app.db.models import AuditEvent, ProjectVersion, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.cad.canonical_export import (
    CanonicalCadRequestRejected,
    run_canonical_cad_export,
)
from app.domains.cad.capability import probe_capabilities
from app.domains.cad.config import CadConfig
from app.domains.cad.errors import CadError
from app.domains.cad.schemas import artifact_out, job_out
from app.domains.foundation.service import error, resolve_project, resolve_world_model

from .change_impact import plan_change_impact
from .persistence import get_current_model, get_model_revision, model_summary, persist_model
from .schemas import ArchitecturalModel

router = APIRouter(tags=["architectural-model"])


class ModelCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: ArchitecturalModel
    expected_revision: int | None = Field(default=None, ge=0)
    source: str = Field(default="bootstrap", min_length=1, max_length=80)
    change_summary: str = Field(default="Initial canonical architectural model", max_length=2_000)


class ModelRevertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_revision: int = Field(ge=1)


class CanonicalCadExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requested_outputs: list[str] | None = None


@router.get("/projects/{project_id}/model")
async def get_canonical_model(project_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    await resolve_project(session, project_id, user.id)
    current = await get_current_model(session, project_id)
    if current is None:
        raise HTTPException(404, {"error": {"code": "MODEL_NOT_INITIALIZED", "message": "No canonical architectural model has been committed"}})
    row, model = current
    return {"read_only": True, **model_summary(row, model)}


@router.get("/projects/{project_id}/model/revisions")
async def list_canonical_model_revisions(project_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    await resolve_project(session, project_id, user.id)
    rows = list((await session.scalars(select(ArchitecturalModelRevision).where(ArchitecturalModelRevision.project_id == project_id).order_by(ArchitecturalModelRevision.revision.desc()))).all())
    return {"read_only": True, "revisions": [
        {"revision": row.revision, "model_hash": row.model_hash, "project_version_id": row.project_version_id,
         "parent_revision_id": row.parent_revision_id, "source": row.source, "change_summary": row.change_summary,
         "created_at": row.created_at.isoformat(), "created_by": row.created_by}
        for row in rows
    ]}


@router.get("/projects/{project_id}/model/revisions/{revision}")
async def get_canonical_model_revision(project_id: str, revision: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    await resolve_project(session, project_id, user.id)
    row, model = await get_model_revision(session, project_id, revision)
    return {"read_only": True, **model_summary(row, model)}


@router.post("/projects/{project_id}/model/revisions/{revision}/revert", status_code=201)
async def revert_canonical_model_revision(project_id: str, revision: int, request: ModelRevertRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    project, membership = await resolve_project(session, project_id, user.id, write=True)
    if membership.role == "viewer": raise HTTPException(403, "Viewer cannot edit projects")
    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None: raise HTTPException(409, {"error": {"code": "VERSION_NOT_READY", "message": "Project has no current version"}})
    current = await get_current_model(session, project_id)
    if current is None or current[0].revision != request.expected_revision:
        raise HTTPException(409, {"error": {"code": "MODEL_REVISION_CONFLICT", "message": "The canonical model changed since it was read"}})
    current_row, current_model = current
    target_row, target_model = await get_model_revision(session, project_id, revision)
    if revision == request.expected_revision:
        raise HTTPException(409, {"error": {"code": "MODEL_REVERT_NOOP", "message": "Cannot revert the canonical model to its current revision"}})
    reverted = target_model.model_copy(update={"revision": request.expected_revision + 1})
    impact = plan_change_impact(current_model, reverted)
    row = await persist_model(session, project=project, version=version, model=reverted, actor_id=user.id,
                              expected_revision=request.expected_revision, parent_revision_id=current_row.id,
                              source="revert", change_summary=f"Revert to architectural model revision {revision}")
    session.add(AuditEvent(organization_id=project.organization_id, project_id=project.id, project_version_id=version.id,
                           actor_user_id=user.id, action="ARCHITECTURAL_MODEL_REVERTED", resource_type="architectural_model_revision",
                           resource_id=row.id, metadata_json={"from_revision": request.expected_revision, "target_revision": target_row.revision,
                           "result_revision": row.revision, "invalidated_artifacts": list(impact.invalidated_artifacts)}))
    await session.commit()
    return {"read_only": False, **model_summary(row, reverted), "impact": {
        "changed_elements": [{"element_id": change.element_id, "change_type": change.change_type} for change in impact.changed_elements],
        "invalidated_artifacts": list(impact.invalidated_artifacts)}}


@router.post("/projects/{project_id}/model/commit", status_code=201)
async def commit_canonical_model(project_id: str, request: ModelCommitRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    project, membership = await resolve_project(session, project_id, user.id, write=True)
    if membership.role == "viewer": raise HTTPException(403, "Viewer cannot edit projects")
    if request.model.project_id != project_id: raise HTTPException(422, "Model project_id does not match route project_id")
    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None: raise HTTPException(409, {"error": {"code": "VERSION_NOT_READY", "message": "Project has no current version"}})
    if await get_current_model(session, project_id) is not None:
        raise HTTPException(409, {"error": {"code": "EDIT_COMMIT_REQUIRED", "message": "Existing canonical models must be changed through the deterministic edit command API"}})
    if request.model.revision != 1:
        raise HTTPException(422, {"error": {"code": "INVALID_INITIAL_REVISION", "message": "Initial canonical model must be revision 1"}})
    row = await persist_model(session, project=project, version=version, model=request.model, actor_id=user.id,
                              expected_revision=0, source="bootstrap", change_summary=request.change_summary)
    await session.commit()
    return {"read_only": False, **model_summary(row, request.model)}


@router.post("/projects/{project_id}/model/cad", status_code=201)
async def export_canonical_model_to_cad(
    project_id: str,
    body: CanonicalCadExportRequest | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Export the current canonical architectural model through the real CAD worker.

    The canonical model is authoritative. The endpoint never accepts geometry or
    dimensions from the client; it only permits narrowing the deployment's enabled
    artifact set. The resulting run and artifacts use the existing CAD persistence,
    validation and content-addressed storage path.
    """
    project, membership = await resolve_project(session, project_id, user.id, write=True)
    if membership.role == "viewer":
        raise HTTPException(403, "Viewer cannot export CAD")

    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None or version.status != "COMMITTED":
        raise error(409, "VERSION_NOT_READY", "Commit the current project version before CAD export")

    current = await get_current_model(session, project_id)
    if current is None:
        raise error(409, "MODEL_NOT_INITIALIZED", "No canonical architectural model has been committed")
    model_row, model = current
    world = await resolve_world_model(session, version.id)
    if model.project_id != project_id:
        raise error(409, "MODEL_PROJECT_MISMATCH", "Canonical model does not belong to this project")

    config = CadConfig.from_settings()
    if config.geometry_engine != "cad_bim":
        raise error(409, "CAD_ENGINE_DISABLED", "CAD geometry generation is disabled on this deployment")
    try:
        capabilities = probe_capabilities(config)
    except CadError as exc:
        raise error(503, "CAD_TOOLCHAIN_UNAVAILABLE", "The configured CAD toolchain is unavailable") from exc

    try:
        outcome = await run_canonical_cad_export(
            session,
            project=project,
            version=version,
            model=model,
            actor_id=user.id,
            config=config,
            capabilities=capabilities,
            requested_outputs=body.requested_outputs if body else None,
            world=world,
        )
    except CanonicalCadRequestRejected as exc:
        raise error(400, exc.code, exc.message) from exc

    if outcome.unavailable:
        raise error(503, outcome.error_code or "CAD_TOOLCHAIN_UNAVAILABLE", outcome.error_message or "CAD toolchain unavailable")
    if outcome.run is None:
        raise error(500, "CAD_RUN_MISSING", "CAD export completed without a persisted run")

    payload = job_out(outcome.run, current_hash=world.model_hash or "", stale=outcome.stale)
    return {
        **payload.model_dump(mode="json"),
        "canonical_model_revision": model_row.revision,
        "canonical_model_hash": model_row.model_hash,
        "artifacts": [artifact_out(row, version.id).model_dump(mode="json") for row in outcome.artifacts],
        "validation_run_id": outcome.validation_run_id,
    }


from .commit_routes import router as commit_router
router.include_router(commit_router)
from .scene_routes import router as scene_router
router.include_router(scene_router)
