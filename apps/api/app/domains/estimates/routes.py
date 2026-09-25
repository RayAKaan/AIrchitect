from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Project, User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from .schemas import EstimateRequest, EstimateResponse
from .engine import calculate

router = APIRouter(prefix='/estimates', tags=['quantity-and-cost'])

@router.post('/calculate', response_model=EstimateResponse)
async def calculate_estimate(body: EstimateRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> EstimateResponse:
    project = await session.get(Project, body.project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    await require_membership(project.organization_id, user, session)
    return calculate(body)
