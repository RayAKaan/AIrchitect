import json
from io import BytesIO
from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from app.db.models import Project, User, ReviewRecord, DeliverableRecord, AuditEvent
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from .schemas import ReviewCreate, ReviewOut, DeliverableCreate

router=APIRouter(prefix='/reviews',tags=['review-deliverables'])

def out(r):
    return ReviewOut(id=r.id,project_id=r.project_id,artifact_id=r.artifact_id,artifact_version=r.artifact_version,source_hash=r.source_hash,reviewer_user_id=r.reviewer_user_id,decision=r.decision,rationale=r.rationale,created_at=r.created_at.isoformat())

@router.post('',response_model=ReviewOut,status_code=201)
async def create_review(body: ReviewCreate,user: User=Depends(current_user),session: AsyncSession=Depends(get_session)):
    project=await session.get(Project,body.project_id)
    if project is None: raise HTTPException(404,'Project not found')
    await require_membership(project.organization_id,user,session,{'owner','admin','member'})
    r=ReviewRecord(organization_id=project.organization_id,project_id=project.id,artifact_id=body.artifact_id,artifact_version=body.artifact_version,source_hash=body.source_hash,reviewer_user_id=user.id,decision=body.decision,rationale=body.rationale)
    session.add(r); session.add(AuditEvent(organization_id=project.organization_id,actor_user_id=user.id,action='feasibility.review_recorded',resource_type='review',resource_id=r.id))
    await session.commit(); await session.refresh(r); return out(r)

@router.get('/{project_id}',response_model=list[ReviewOut])
async def list_reviews(project_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    project=await session.get(Project,project_id)
    if project is None: raise HTTPException(404,'Project not found')
    await require_membership(project.organization_id,user,session)
    rows=await session.scalars(select(ReviewRecord).where(ReviewRecord.project_id==project_id).order_by(ReviewRecord.created_at.desc()))
    return [out(r) for r in rows.all()]

@router.post('/deliverables/json')
async def create_json_deliverable(body:DeliverableCreate,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    project=await session.get(Project,body.project_id)
    if project is None: raise HTTPException(404,'Project not found')
    await require_membership(project.organization_id,user,session,{'owner','admin','member'})
    payload=body.model_dump(); payload.update({'project_name':project.name,'generated_by':user.id,'disclaimer':'Preliminary feasibility output only; not regulatory approval, engineering certification, or permission to construct.'})
    row=DeliverableRecord(organization_id=project.organization_id,project_id=project.id,artifact_id=body.artifact_id,artifact_version=body.artifact_version,source_hash=body.source_hash,format='json',payload_json=payload,created_by=user.id)
    session.add(row); await session.commit()
    return {'deliverable_id':row.id,'format':'json','payload':payload,'immutable_record':False,'note':'Record is stored, but immutability and source-hash verification are not yet enforced.'}

@router.post('/deliverables/pdf')
async def create_pdf_deliverable(body:DeliverableCreate,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    project=await session.get(Project,body.project_id)
    if project is None: raise HTTPException(404,'Project not found')
    await require_membership(project.organization_id,user,session,{'owner','admin','member'})
    payload=body.model_dump(); payload.update({'project_name':project.name,'generated_by':user.id,'disclaimer':'Preliminary feasibility output only; not regulatory approval, engineering certification, or permission to construct.'})
    row=DeliverableRecord(organization_id=project.organization_id,project_id=project.id,artifact_id=body.artifact_id,artifact_version=body.artifact_version,source_hash=body.source_hash,format='pdf',payload_json=payload,created_by=user.id)
    session.add(row); await session.commit()
    buf=BytesIO(); c=canvas.Canvas(buf,pagesize=A4); width,height=A4; y=height-55
    c.setFont('Helvetica-Bold',16); c.drawString(48,y,body.title[:90]); y-=28
    c.setFont('Helvetica',9)
    lines=[f'Project: {project.name}',f'Artifact: {body.artifact_id} / {body.artifact_version}',f'Source hash: {body.source_hash}',f'Validation: {body.validation_status} | Current: {body.current}', '',body.summary, '',payload['disclaimer'],'','Sections (JSON):',json.dumps(body.sections,ensure_ascii=True,indent=2)]
    for line in '\n'.join(lines).splitlines():
        if y<55: c.showPage(); y=height-55; c.setFont('Helvetica',9)
        c.drawString(48,y,line[:115]); y-=13
    c.save()
    return Response(buf.getvalue(),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="feasibility-{row.id}.pdf"','X-Deliverable-Id':row.id,'X-Source-Hash':body.source_hash})
