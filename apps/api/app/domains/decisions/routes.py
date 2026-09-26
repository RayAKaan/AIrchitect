from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Membership,Project,ProjectVersion,User
from app.db.session import get_session
from app.dependencies import current_user
from .runtime import DecisionRuntime
from .schemas import DecisionRequest,DecisionResponse

router=APIRouter(prefix='/decisions',tags=['decisions'])

@router.post('/evaluate',response_model=DecisionResponse)
async def evaluate(body:DecisionRequest,user:User=Depends(current_user),session:AsyncSession=Depends(get_session))->DecisionResponse:
 project=None
 if body.project_version_id:
  project=await session.scalar(select(Project).join(ProjectVersion,ProjectVersion.project_id==Project.id).join(Membership,Membership.organization_id==Project.organization_id).where(ProjectVersion.id==body.project_version_id,Membership.user_id==user.id))
  if project is None: raise HTTPException(404,'Project version not found')
 try: result=await DecisionRuntime().evaluate(session,body,project)
 except RuntimeError as exc: raise HTTPException(503,str(exc)) from exc
 except ValueError as exc: raise HTTPException(422,str(exc)) from exc
 await session.commit(); return result
