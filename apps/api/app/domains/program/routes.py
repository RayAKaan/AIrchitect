from fastapi import APIRouter, Depends
from app.db.models import User
from app.db.session import get_session
from app.dependencies import current_user
from .service import generate

router = APIRouter(tags=["architectural-program"])

@router.post("/projects/{project_id}/versions/{version_ref}/program/generate")
async def generate_program(project_id: str, version_ref: str, user: User = Depends(current_user), session=Depends(get_session)):
    return await generate(session, project_id, version_ref, user)
