from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Project, User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from .engine import generate
from .schemas import GeometryGenerateRequest, GeometryGenerateResponse

router = APIRouter(prefix='/geometry', tags=['geometry'])

@router.post('/generate', response_model=GeometryGenerateResponse)
async def generate_geometry(body: GeometryGenerateRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> GeometryGenerateResponse:
    project = await session.get(Project, body.project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    await require_membership(project.organization_id, user, session)
    return GeometryGenerateResponse(
        project_id=project.id, source_revision=body.source_revision, artifacts=generate(body),
        caveats=['Conceptual rectangular massing only; not a site-boundary or BIM model.',
                 'Setbacks are user-supplied geometric inputs, not verified regulatory requirements.',
                 'No structural, fire/life-safety, planning, or engineering approval is implied.'],
    )
