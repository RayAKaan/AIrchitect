from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.architectural_model_models import ArchitecturalModelRevision
from app.db.models import AuditEvent, ProjectVersion, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.foundation.service import resolve_project

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

from .commit_routes import router as commit_router
router.include_router(commit_router)
from .scene_routes import router as scene_router
router.include_router(scene_router)
