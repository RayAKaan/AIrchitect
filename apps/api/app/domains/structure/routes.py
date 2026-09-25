from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Project, User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from .engine import generate
from .schemas import StructuralConceptRequest, StructuralConceptResponse

router = APIRouter(prefix='/structure', tags=['structural-workflow'])


@router.post('/concept', response_model=StructuralConceptResponse)
async def create_structural_concept(body: StructuralConceptRequest,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> StructuralConceptResponse:
    project = await session.get(Project, body.project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    await require_membership(project.organization_id, user, session)
    return generate(body)
