from fastapi import APIRouter, Depends
from app.db.models import User
from app.db.session import get_session
from app.dependencies import current_user
from .schemas import BriefWrite
from .service import latest, write, history

router = APIRouter(tags=["brief"])

@router.get("/projects/{project_id}/versions/{version_ref}/brief")
async def get_brief(project_id: str, version_ref: str, user: User = Depends(current_user), session=Depends(get_session)):
    return {"brief": await latest(session, project_id, version_ref, user)}

@router.put("/projects/{project_id}/versions/{version_ref}/brief")
async def put_brief(project_id: str, version_ref: str, body: BriefWrite, user: User = Depends(current_user), session=Depends(get_session)):
    return await write(session, project_id, version_ref, body, user)

@router.get("/projects/{project_id}/versions/{version_ref}/brief/history")
async def get_brief_history(project_id: str, version_ref: str, user: User = Depends(current_user), session=Depends(get_session)):
    return await history(session, project_id, version_ref, user)
