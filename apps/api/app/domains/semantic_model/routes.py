from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session
from app.dependencies import current_user
from app.domains.foundation.service import resolve_project_version, resolve_world_model
from app.domains.semantic_model.service import compile_parametric_geometry, compile_semantic_model

router = APIRouter(tags=["semantic-building-model"])


async def _canonical(project_id: str, version_ref: str, user: User, session: AsyncSession):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id)
    world = await resolve_world_model(session, version.id)
    semantic = world.model_json.get("semantic_model")
    if not isinstance(semantic, dict) or not semantic.get("elements"):
        # Backward-compatible deterministic projection for pre-Phase-24 revisions.
        semantic = compile_semantic_model(world.model_json)
    return project, version, world, semantic


@router.get("/projects/{project_id}/versions/{version_ref}/semantic-model")
async def get_semantic_model(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return the immutable semantic graph attached to the verified canonical revision."""
    project, version, world, semantic = await _canonical(project_id, version_ref, user, session)
    return {
        "project_id": project.id,
        "project_version_id": version.id,
        "world_model_revision_id": world.id,
        "world_model_revision": world.revision,
        "world_model_hash": world.model_hash,
        "semantic_model": semantic,
    }


@router.get("/projects/{project_id}/versions/{version_ref}/semantic-model/parametric-geometry")
async def get_parametric_geometry_spec(
    project_id: str,
    version_ref: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return deterministic CAD/BIM feature intents and explicit missing-input gates."""
    project, version, world, semantic = await _canonical(project_id, version_ref, user, session)
    spec = compile_parametric_geometry(world.model_json, semantic)
    return {
        "project_id": project.id,
        "project_version_id": version.id,
        "world_model_revision_id": world.id,
        "world_model_revision": world.revision,
        "world_model_hash": world.model_hash,
        "specification": spec,
    }
