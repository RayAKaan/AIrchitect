from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ArtifactVersion,Project,User,WorldModelRevision
from app.db.session import get_session
from app.dependencies import current_user,require_membership
from app.domains.foundation.service import resolve_project_version
from .engine import analyze
from .schemas import ChangeImpactRequest,ChangeImpactResponse
router=APIRouter(tags=['change-impact'])
@router.post('/change-impact/analyze',response_model=ChangeImpactResponse)
async def analyze_change(body:ChangeImpactRequest,user:User=Depends(current_user),session:AsyncSession=Depends(get_session))->ChangeImpactResponse:
 project=await session.get(Project,body.project_id)
 if project is None:raise HTTPException(404,'Project not found')
 await require_membership(project.organization_id,user,session);return analyze(body)

def flatten(value,prefix=''):
 out={}
 if isinstance(value,dict):
  for k,v in value.items():out.update(flatten(v,f'{prefix}.{k}' if prefix else k))
 else:out[prefix]=value
 return out
@router.get('/projects/{project_id}/versions/{version_ref}/change-impact')
async def persisted_impact(project_id:str,version_ref:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
 _,version=await resolve_project_version(session,project_id,version_ref,user.id);current=await session.scalar(select(WorldModelRevision).where(WorldModelRevision.project_version_id==version.id).order_by(WorldModelRevision.revision.desc()))
 previous=None
 if version.parent_version_id:previous=await session.scalar(select(WorldModelRevision).where(WorldModelRevision.project_version_id==version.parent_version_id).order_by(WorldModelRevision.revision.desc()))
 before=flatten(previous.model_json) if previous else {};after=flatten(current.model_json);changed=sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
 artifacts=list((await session.scalars(select(ArtifactVersion).where(ArtifactVersion.project_version_id.in_([x for x in [version.id,version.parent_version_id] if x])))).all())
 affected=[];unaffected=[]
 for x in artifacts:
  item={'artifact_version_id':x.id,'artifact_type':x.artifact_type,'version':x.version,'status':x.status,'reason':('World Model input changed; dependency-driven recomputation is required.' if x.status.upper()=='STALE' else 'Stored dependency and source hashes remain current for this project version.'),'immutable':True}
  (affected if x.status.upper()=='STALE' else unaffected).append(item)
 return {'project_id':project_id,'project_version_id':version.id,'parent_version_id':version.parent_version_id,'changed_fields':changed,'affected':affected,'unaffected':unaffected,'selective_recomputation':True,'old_artifacts_immutable':True}
