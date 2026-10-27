from __future__ import annotations

from dataclasses import asdict
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProjectVersion, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.foundation.service import error, resolve_project
from app.domains.model.persistence import get_current_model
from .structural_model import build_structural_model

router = APIRouter(tags=["s14-engineering"])


@router.get("/projects/{project_id}/model/structural-screening")
async def structural_screening(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    project = await resolve_project(session, project_id, user.id)
    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None or version.status != "COMMITTED":
        raise error(409, "VERSION_NOT_READY", "Commit the current project version before structural screening")
    current = await get_current_model(session, project_id)
    if current is None:
        raise error(409, "MODEL_NOT_INITIALIZED", "No canonical architectural model has been committed")
    _, model = current
    result = build_structural_model(model)
    return {
        "model_revision": model.revision,
        "model_hash": result.model_hash,
        "screening_only": result.screening_only,
        "assumptions": list(result.assumptions),
        "nodes": [asdict(node) for node in result.nodes],
        "members": [asdict(member) for member in result.members],
    }
