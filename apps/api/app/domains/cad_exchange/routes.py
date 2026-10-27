from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProjectVersion, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.foundation.service import error, resolve_project
from app.domains.model import model_hash
from app.domains.model.persistence import get_current_model

from .dxf import render_dxf

router = APIRouter(tags=["s14-cad-exchange"])


@router.get("/projects/{project_id}/model/dxf")
async def export_canonical_dxf(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Export committed canonical architectural linework as deterministic DXF."""
    project = await resolve_project(session, project_id, user.id)
    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None or version.status != "COMMITTED":
        raise error(409, "VERSION_NOT_READY", "Commit the current project version before DXF export")
    current = await get_current_model(session, project_id)
    if current is None:
        raise error(409, "MODEL_NOT_INITIALIZED", "No canonical architectural model has been committed")
    _, model = current
    payload = render_dxf(model)
    digest = model_hash(model)
    return Response(
        content=payload,
        media_type="application/dxf",
        headers={
            "Content-Disposition": f'attachment; filename="airchitect-r{model.revision}-{digest[:12]}.dxf"',
            "X-Canonical-Model-Revision": str(model.revision),
            "X-Canonical-Model-Hash": digest,
        },
    )
