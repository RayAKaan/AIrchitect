from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProjectVersion, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.foundation.service import resolve_project

from .persistence import get_current_model, get_model_revision, model_summary, persist_model
from .schemas import ArchitecturalModel

router = APIRouter(tags=["architectural-model"])


class ModelCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: ArchitecturalModel
    expected_revision: int | None = Field(default=None, ge=0)
    source: str = Field(default="user", min_length=1, max_length=80)
    change_summary: str = Field(default="", max_length=2_000)


@router.get("/projects/{project_id}/model")
async def get_canonical_model(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    await resolve_project(session, project_id, user.id)
    current = await get_current_model(session, project_id)
    if current is None:
        raise HTTPException(404, {"error": {"code": "MODEL_NOT_INITIALIZED", "message": "No canonical architectural model has been committed"}})
    row, model = current
    return {"read_only": True, **model_summary(row, model)}


@router.get("/projects/{project_id}/model/revisions/{revision}")
async def get_canonical_model_revision(
    project_id: str,
    revision: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    await resolve_project(session, project_id, user.id)
    row, model = await get_model_revision(session, project_id, revision)
    return {"read_only": True, **model_summary(row, model)}


@router.post("/projects/{project_id}/model/commit", status_code=201)
async def commit_canonical_model(
    project_id: str,
    request: ModelCommitRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    project, membership = await resolve_project(session, project_id, user.id, write=True)
    if membership.role == "viewer":
        raise HTTPException(403, "Viewer cannot edit projects")
    if request.model.project_id != project_id:
        raise HTTPException(422, "Model project_id does not match route project_id")
    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None:
        raise HTTPException(409, {"error": {"code": "VERSION_NOT_READY", "message": "Project has no current version"}})
    current = await get_current_model(session, project_id)
    current_revision = current[0].revision if current else 0
    if request.expected_revision is not None and request.expected_revision != current_revision:
        raise HTTPException(409, {"error": {"code": "MODEL_REVISION_CONFLICT", "message": "The canonical model changed since it was read", "context": {"current_revision": current_revision}}})
    row = await persist_model(
        session,
        project=project,
        version=version,
        model=request.model,
        actor_id=user.id,
        expected_revision=request.expected_revision,
        source=request.source,
        change_summary=request.change_summary,
    )
    await session.commit()
    return {"read_only": False, **model_summary(row, request.model)}
