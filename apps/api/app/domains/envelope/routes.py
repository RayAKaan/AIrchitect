from fastapi import APIRouter, Depends
from app.db.models import User
from app.db.session import get_session
from app.dependencies import current_user
from .schemas import EnvelopeRequest
from .service import generate

router = APIRouter(tags=["planning-envelope"])

@router.post("/projects/{project_id}/versions/{version_ref}/envelope/generate")
async def generate_envelope(project_id: str, version_ref: str, body: EnvelopeRequest, user: User = Depends(current_user), session=Depends(get_session)):
    return await generate(session, project_id, version_ref, body, user)
