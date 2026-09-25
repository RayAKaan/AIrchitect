from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Project, WorldModelRevision, AuditEvent, User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from app.domains.world_model.schemas import BuildingModel, WorldModelMutation

router = APIRouter(tags=['world-model'])

async def _project(project_id: str, user: User, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    await require_membership(project.organization_id, user, session)
    return project

@router.get('/projects/{project_id}/world-model')
async def get_world_model(project_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await _project(project_id, user, session)
    row = await session.scalar(select(WorldModelRevision).where(WorldModelRevision.project_id == project_id).order_by(WorldModelRevision.revision.desc()).limit(1))
    if row is None:
        return {'project_id': project_id, 'project_version': project.version, 'revision': 0, 'model': BuildingModel().model_dump()}
    return {'project_id': project_id, 'project_version': project.version, 'revision': row.revision, 'model': row.model_json}

@router.put('/projects/{project_id}/world-model')
async def mutate_world_model(project_id: str, body: WorldModelMutation, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await _project(project_id, user, session)
    await require_membership(project.organization_id, user, session, {'owner', 'admin', 'member'})
    if project.version != body.expected_project_version:
        raise HTTPException(409, {'message': 'Project version conflict', 'current_version': project.version})
    latest = await session.scalar(select(func.max(WorldModelRevision.revision)).where(WorldModelRevision.project_id == project_id))
    revision = (latest or 0) + 1
    row = WorldModelRevision(organization_id=project.organization_id, project_id=project_id, revision=revision, model_json=body.model.model_dump(mode='json'), created_by=user.id)
    project.version += 1
    session.add(row)
    session.add(AuditEvent(organization_id=project.organization_id, actor_user_id=user.id, action='world_model.revised', resource_type='project', resource_id=project_id))
    await session.commit()
    return {'project_id': project_id, 'project_version': project.version, 'revision': revision, 'model': row.model_json}

@router.get('/projects/{project_id}/world-model/revisions')
async def list_world_model_revisions(project_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await _project(project_id, user, session)
    rows = await session.scalars(select(WorldModelRevision).where(WorldModelRevision.project_id == project_id).order_by(WorldModelRevision.revision.desc()))
    return [{'id': r.id, 'revision': r.revision, 'created_by': r.created_by, 'created_at': r.created_at.isoformat()} for r in rows]
