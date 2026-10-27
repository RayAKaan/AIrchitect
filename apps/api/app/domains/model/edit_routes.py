from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.db.models import User
from app.dependencies import current_user

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
) -> dict[str, object]:
    # The preview endpoint deliberately reads a durable revision and never accepts
    # an arbitrary client-supplied model as authoritative state.
    from app.db.session import get_session
    from fastapi import Request
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import Depends as _Depends

    raise RuntimeError("route dependency placeholder")
