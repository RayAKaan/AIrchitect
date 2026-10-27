from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent, ProjectVersion, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.foundation.service import resolve_project

from .commit_service import commit_edit_batch
from .edit_commands import EditCommand
from .persistence import model_summary

router = APIRouter(tags=["architectural-model"])


class EditCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_revision: int = Field(ge=1)
    commands: tuple[EditCommand, ...] = Field(min_length=1, max_length=100)
    change_summary: str = Field(default="Architectural model edit", min_length=1, max_length=2_000)


@router.post("/projects/{project_id}/model/edits", status_code=201)
async def commit_edit(
    project_id: str,
    request: EditCommitRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    project, membership = await resolve_project(session, project_id, user.id, write=True)
    if membership.role == "viewer":
        raise HTTPException(403, "Viewer cannot edit projects")
    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None:
        raise HTTPException(409, {"error": {"code": "VERSION_NOT_READY", "message": "Project has no current version"}})
    try:
        row, model, impact = await commit_edit_batch(
            session,
            project=project,
            version=version,
            actor_id=user.id,
            expected_revision=request.expected_revision,
            commands=request.commands,
            change_summary=request.change_summary,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    session.add(AuditEvent(
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        actor_user_id=user.id,
        action="ARCHITECTURAL_MODEL_EDIT_COMMITTED",
        resource_type="architectural_model_revision",
        resource_id=row.id,
        metadata_json={
            "revision": row.revision,
            "model_hash": row.model_hash,
            "changed_elements": [
                {"element_id": change.element_id, "change_type": change.change_type}
                for change in impact.changed_elements
            ],
            "invalidated_artifacts": list(impact.invalidated_artifacts),
        },
    ))
    await session.commit()
    return {
        "read_only": False,
        "model": model_summary(row, model),
        "impact": {
            "previous_hash": impact.previous_hash,
            "current_hash": impact.current_hash,
            "changed_elements": [
                {"element_id": change.element_id, "change_type": change.change_type}
                for change in impact.changed_elements
            ],
            "affected_elements": list(impact.affected_elements),
            "invalidated_artifacts": list(impact.invalidated_artifacts),
        },
    }
