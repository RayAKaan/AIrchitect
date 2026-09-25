from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Project, User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from .engine import evaluate
from .schemas import RegulatoryEvaluationRequest, RegulatoryEvaluationResponse

router = APIRouter(prefix='/regulatory', tags=['regulatory-screening'])

@router.post('/evaluate', response_model=RegulatoryEvaluationResponse)
async def evaluate_regulatory(body: RegulatoryEvaluationRequest,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> RegulatoryEvaluationResponse:
    project = await session.get(Project, body.project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    await require_membership(project.organization_id, user, session)
    return evaluate(body)
