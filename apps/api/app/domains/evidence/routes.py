from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import or_,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import EvidenceLink,EvidenceNode,Project,User
from app.db.session import get_session
from app.dependencies import current_user,require_membership
router=APIRouter(tags=['evidence'])
def node_out(n):return {'id':n.id,'project_version_id':n.project_version_id,'workflow_id':n.workflow_id,'source_id':n.source_id,'source_type':n.source_type,'source_hash':n.source_hash,'evidence_hash':n.evidence_hash,'label':n.label,'payload':n.payload_json,'provenance':n.provenance_json,'created_at':n.created_at}
async def scope(project_id,user,session):
 p=await session.get(Project,project_id)
 if p is None:raise HTTPException(404,'Project not found')
 await require_membership(p.organization_id,user,session);return p
@router.get('/projects/{project_id}/evidence')
async def list_evidence(project_id:str,version_id:str|None=None,source_type:str|None=None,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
 await scope(project_id,user,session);q=select(EvidenceNode).where(EvidenceNode.project_id==project_id)
 if version_id:q=q.where(EvidenceNode.project_version_id==version_id)
 if source_type:q=q.where(EvidenceNode.source_type==source_type)
 rows=(await session.scalars(q.order_by(EvidenceNode.created_at))).all();return {'nodes':[node_out(x) for x in rows]}
@router.get('/projects/{project_id}/evidence/{node_id}')
async def get_evidence(project_id:str,node_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
 await scope(project_id,user,session);node=await session.scalar(select(EvidenceNode).where(EvidenceNode.id==node_id,EvidenceNode.project_id==project_id))
 if node is None:raise HTTPException(404,'Evidence node not found')
 links=(await session.scalars(select(EvidenceLink).where(or_(EvidenceLink.from_node_id==node.id,EvidenceLink.to_node_id==node.id)))).all();return {'node':node_out(node),'links':[{'id':x.id,'from_node_id':x.from_node_id,'to_node_id':x.to_node_id,'relation':x.relation} for x in links]}
@router.get('/projects/{project_id}/evidence/graph/view')
async def graph(project_id:str,version_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
 await scope(project_id,user,session);nodes=(await session.scalars(select(EvidenceNode).where(EvidenceNode.project_id==project_id,EvidenceNode.project_version_id==version_id))).all();ids=[x.id for x in nodes];links=[] if not ids else (await session.scalars(select(EvidenceLink).where(EvidenceLink.from_node_id.in_(ids),EvidenceLink.to_node_id.in_(ids)))).all();return {'nodes':[node_out(x) for x in nodes],'links':[{'id':x.id,'from_node_id':x.from_node_id,'to_node_id':x.to_node_id,'relation':x.relation} for x in links]}
