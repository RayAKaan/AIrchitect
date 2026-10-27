from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProjectVersion, User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.foundation.service import error, resolve_project
from app.domains.model.persistence import get_current_model
from .ifc_semantics import project_architectural_semantics

router = APIRouter(tags=["s14-bim"])


@router.get("/projects/{project_id}/model/ifc-semantics")
async def get_canonical_ifc_semantics(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Expose the canonical model's IFC4 semantic projection for BIM consumers."""
    project = await resolve_project(session, project_id, user.id)
    version = await session.get(ProjectVersion, project.current_version_id)
    if version is None or version.status != "COMMITTED":
        raise error(409, "VERSION_NOT_READY", "Commit the current project version before BIM projection")
    current = await get_current_model(session, project_id)
    if current is None:
        raise error(409, "MODEL_NOT_INITIALIZED", "No canonical architectural model has been committed")
    _, model = current
    projection = project_architectural_semantics(model)
    return {
        "schema": projection.schema,
        "model_revision": model.revision,
        "model_hash": projection.model_hash,
        "entities": [
            {
                "source_id": entity.source_id,
                "ifc_class": entity.ifc_class,
                "name": entity.name,
                "level_id": entity.level_id,
                "properties": dict(entity.properties),
            }
            for entity in projection.entities
        ],
        "relationships": [list(item) for item in projection.relationships],
    }
