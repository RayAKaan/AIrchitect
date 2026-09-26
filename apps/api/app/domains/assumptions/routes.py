from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AssumptionRecord, Project, User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from app.domains.assumptions.schemas import AssumptionCreate, AssumptionOut, AssumptionTransition, AssumptionReplace

router = APIRouter(tags=["assumptions"])


async def _project(project_id: str, user: User, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
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
    rows = await session.scalars(select(AssumptionRecord).where(
        AssumptionRecord.project_id == project_id).order_by(AssumptionRecord.created_at.desc()))
    return [_out(row) for row in rows.all()]


def legacy_disabled() -> None:
    raise HTTPException(410, {"error": {"code": "CANONICAL_VERSION_REQUIRED",
        "message": "Project-scoped assumption mutation is disabled; use the version-scoped Phase 1 API."}})


@router.post('/projects/{project_id}/assumptions', response_model=AssumptionOut, status_code=201)
async def create_assumption(project_id: str, body: AssumptionCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await _project(project_id, user, session)
    await require_membership(project.organization_id, user, session, {'owner', 'admin', 'member'})
    legacy_disabled()


@router.post('/projects/{project_id}/assumptions/{assumption_id}/transition', response_model=AssumptionOut)
async def transition_assumption(project_id: str, assumption_id: str, body: AssumptionTransition, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await _project(project_id, user, session)
    await require_membership(project.organization_id, user, session, {'owner', 'admin', 'member'})
    legacy_disabled()


@router.post('/projects/{project_id}/assumptions/{assumption_id}/replace', response_model=AssumptionOut, status_code=201)
async def replace_assumption(project_id: str, assumption_id: str, body: AssumptionReplace, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await _project(project_id, user, session)
    await require_membership(project.organization_id, user, session, {'owner', 'admin', 'member'})
    legacy_disabled()
