from __future__ import annotations

from fastapi import APIRouter, Depends
from app.db.models import User
from app.dependencies import current_user
from .preview import preview_command
from .schemas import CommandEnvelope, CommandPreview

router = APIRouter(tags=["commands"])


@router.post("/commands/preview", response_model=CommandPreview)
async def preview(body: CommandEnvelope, user: User = Depends(current_user)) -> CommandPreview:
    """Validate a proposed command without mutating canonical state."""
    return preview_command(body)
