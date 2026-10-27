from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.foundation.service import resolve_project

from .edit_batch import apply_edit_batch
from .edit_commands import EditCommand
from .persistence import get_model_revision

router = APIRouter(tags=["architectural-model"])


class EditPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_revision: int = Field(ge=1)
    commands: tuple[EditCommand, ...] = Field(min_length=1, max_length=100)


@router.post("/projects/{project_id}/model/edit-preview")
async def edit_preview(
    project_id: str,
    request: EditPreviewRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    await resolve_project(session, project_id, user.id)
    _, model = await get_model_revision(session, project_id, request.expected_revision)
    try:
        preview = apply_edit_batch(model, request.commands)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "read_only": True,
        "source_revision": model.revision,
        "result_revision": preview.revision,
        "commands": [command.model_dump(mode="json") for command in request.commands],
        "model": preview.model_dump(mode="json", exclude_none=False),
    }
