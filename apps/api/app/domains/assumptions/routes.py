from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AssumptionRecord, AuditEvent, Project, User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from app.domains.assumptions.schemas import AssumptionCreate, AssumptionOut, AssumptionTransition, AssumptionReplace

router = APIRouter(tags=["assumptions"])

async def _project(project_id: str, user: User, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if project is None: raise HTTPException(404, "Project not found")
    await require_membership(project.organization_id, user, session)
    return project

def _out(row: AssumptionRecord) -> AssumptionOut:
    return AssumptionOut(id=row.id, project_id=row.project_id, project_version=row.project_version,
        parameter=row.parameter, value=row.value_json, unit=row.unit, reason=row.reason,
        source=row.source, status=row.status, impact_scope=row.impact_scope_json,
        confidence=row.confidence, created_by=row.created_by, created_at=row.created_at,
        supersedes_id=row.supersedes_id)

@router.get('/projects/{project_id}/assumptions', response_model=list[AssumptionOut])
async def list_assumptions(project_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await _project(project_id, user, session)
    rows = await session.scalars(select(AssumptionRecord).where(AssumptionRecord.project_id == project_id).order_by(AssumptionRecord.created_at.desc()))
    return [_out(row) for row in rows.all()]

@router.post('/projects/{project_id}/assumptions', response_model=AssumptionOut, status_code=201)
async def create_assumption(project_id: str, body: AssumptionCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await _project(project_id, user, session)
    await require_membership(project.organization_id, user, session, {'owner', 'admin', 'member'})
    row = AssumptionRecord(organization_id=project.organization_id, project_id=project.id,
        project_version=project.version, parameter=body.parameter.strip(), value_json={'value': body.value},
        unit=body.unit, reason=body.reason, source=body.source, impact_scope_json=body.impact_scope,
        confidence=body.confidence, created_by=user.id)
    session.add(row)
    session.add(AuditEvent(organization_id=project.organization_id, actor_user_id=user.id,
        action='assumption.proposed', resource_type='assumption', resource_id=row.id))
    await session.commit(); await session.refresh(row)
    return _out(row)

@router.post('/projects/{project_id}/assumptions/{assumption_id}/transition', response_model=AssumptionOut)
async def transition_assumption(project_id: str, assumption_id: str, body: AssumptionTransition, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await _project(project_id, user, session)
    await require_membership(project.organization_id, user, session, {'owner', 'admin', 'member'})
    row = await session.scalar(select(AssumptionRecord).where(AssumptionRecord.id == assumption_id, AssumptionRecord.project_id == project_id))
    if row is None: raise HTTPException(404, 'Assumption not found')
    if row.status != 'proposed': raise HTTPException(409, 'Only proposed assumptions can be accepted or rejected')
    row.status = body.status
    project.version += 1
    row.project_version = project.version
    session.add(AuditEvent(organization_id=project.organization_id, actor_user_id=user.id,
        action=f'assumption.{body.status}', resource_type='assumption', resource_id=row.id))
    await session.commit(); await session.refresh(row)
    return _out(row)

@router.post('/projects/{project_id}/assumptions/{assumption_id}/replace', response_model=AssumptionOut, status_code=201)
async def replace_assumption(project_id: str, assumption_id: str, body: AssumptionReplace, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await _project(project_id, user, session)
    await require_membership(project.organization_id, user, session, {'owner', 'admin', 'member'})
    old = await session.scalar(select(AssumptionRecord).where(AssumptionRecord.id == assumption_id, AssumptionRecord.project_id == project_id))
    if old is None: raise HTTPException(404, 'Assumption not found')
    if old.status not in {'proposed', 'accepted'}: raise HTTPException(409, 'Assumption cannot be replaced from its current state')
    old.status = 'replaced'
    project.version += 1
    data = body.replacement
    row = AssumptionRecord(organization_id=project.organization_id, project_id=project.id, project_version=project.version,
        parameter=data.parameter.strip(), value_json={'value': data.value}, unit=data.unit, reason=data.reason,
        source=data.source, status='proposed', impact_scope_json=data.impact_scope, confidence=data.confidence,
        created_by=user.id, supersedes_id=old.id)
    session.add(row)
    session.add(AuditEvent(organization_id=project.organization_id, actor_user_id=user.id,
        action='assumption.replaced', resource_type='assumption', resource_id=old.id))
    await session.commit(); await session.refresh(row)
    return _out(row)
