from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import User
from app.dependencies import current_user
from app.domains.foundation.service import resolve_project
from app.domains.geometry.scene import build_model_scene

from .persistence import get_current_model

router = APIRouter(tags=["architectural-model"])


@router.get("/projects/{project_id}/model/scene")
async def get_canonical_model_scene(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    await resolve_project(session, project_id, user.id)
    current = await get_current_model(session, project_id)
    if current is None:
        raise HTTPException(404, {"error": {"code": "MODEL_NOT_INITIALIZED", "message": "No canonical architectural model has been committed"}})
    row, model = current
    scene = build_model_scene(model)
    return {
        "read_only": True,
        "revision": row.revision,
        "model_hash": row.model_hash,
        "scene": asdict(scene),
    }
