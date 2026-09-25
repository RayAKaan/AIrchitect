from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Project, User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from .engine import analyze
from .schemas import ChangeImpactRequest, ChangeImpactResponse

router = APIRouter(prefix="/change-impact", tags=["change-impact"])

@router.post("/analyze", response_model=ChangeImpactResponse)
async def analyze_change(body: ChangeImpactRequest,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> ChangeImpactResponse:
    project = await session.get(Project, body.project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    await require_membership(project.organization_id, user, session)
    return analyze(body)
