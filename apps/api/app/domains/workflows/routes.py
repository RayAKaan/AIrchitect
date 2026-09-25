from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Project, WorkflowRecord, WorkflowTaskRecord, User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from .schemas import WorkflowCreate, WorkflowOut, TaskOut

router = APIRouter(prefix='/workflows', tags=['workflows'])

async def load_workflow(workflow_id: str, user: User, session: AsyncSession):
    wf = await session.get(WorkflowRecord, workflow_id)
    if wf is None: raise HTTPException(404, 'Workflow not found')
    await require_membership(wf.organization_id, user, session)
    tasks = list((await session.scalars(select(WorkflowTaskRecord).where(WorkflowTaskRecord.workflow_id == wf.id))).all())
    return wf, tasks

def render(wf, tasks):
    return WorkflowOut(id=wf.id, project_id=wf.project_id, workflow_type=wf.workflow_type, state=wf.state,
        created_at=wf.created_at, tasks=[TaskOut(id=t.id,key=t.key,kind=t.kind,payload=t.payload_json,
        depends_on=t.depends_on_json,state=t.state,attempts=t.attempts,max_attempts=t.max_attempts,
        result=t.result_json,error=t.error) for t in tasks])

def recalc(wf, tasks):
    states = [t.state for t in tasks]
    if all(s == 'succeeded' for s in states): wf.state = 'succeeded'
    elif any(s == 'running' for s in states): wf.state = 'running'
    elif any(s == 'failed' for s in states): wf.state = 'failed'
    elif all(s == 'cancelled' for s in states): wf.state = 'cancelled'
    else: wf.state = 'pending'

@router.post('', response_model=WorkflowOut, status_code=201)
async def create_workflow(body: WorkflowCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    project = await session.get(Project, body.project_id)
    if project is None: raise HTTPException(404, 'Project not found')
    await require_membership(project.organization_id, user, session, {'owner','admin','member'})
    existing = await session.scalar(select(WorkflowRecord).where(WorkflowRecord.organization_id==project.organization_id, WorkflowRecord.idempotency_key==body.idempotency_key))
    if existing:
        tasks = list((await session.scalars(select(WorkflowTaskRecord).where(WorkflowTaskRecord.workflow_id==existing.id))).all())
        return render(existing, tasks)
    wf = WorkflowRecord(organization_id=project.organization_id, project_id=project.id, created_by=user.id, workflow_type=body.workflow_type, idempotency_key=body.idempotency_key)
    session.add(wf); await session.flush()
    for spec in body.tasks:
        session.add(WorkflowTaskRecord(workflow_id=wf.id,key=spec.key,kind=spec.kind,payload_json=spec.payload,depends_on_json=spec.depends_on,max_attempts=spec.max_attempts))
    try: await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(select(WorkflowRecord).where(WorkflowRecord.organization_id==project.organization_id, WorkflowRecord.idempotency_key==body.idempotency_key))
        if existing:
            tasks = list((await session.scalars(select(WorkflowTaskRecord).where(WorkflowTaskRecord.workflow_id==existing.id))).all())
            return render(existing,tasks)
        raise HTTPException(409,'Workflow creation conflict') from None
    wf, tasks = await load_workflow(wf.id,user,session)
    return render(wf,tasks)

@router.get('/{workflow_id}', response_model=WorkflowOut)
async def get_workflow(workflow_id: str, user: User=Depends(current_user), session: AsyncSession=Depends(get_session)):
    wf,tasks=await load_workflow(workflow_id,user,session); return render(wf,tasks)

@router.post('/{workflow_id}/claim', response_model=list[TaskOut])
async def claim_ready(workflow_id: str, user: User=Depends(current_user), session: AsyncSession=Depends(get_session)):
    wf,tasks=await load_workflow(workflow_id,user,session)
    if wf.state in {'cancelled','succeeded','failed'}: return []
    by_key={t.key:t for t in tasks}; claimed=[]
    for task in sorted(tasks,key=lambda t:t.key):
        if task.state != 'pending': continue
        deps=[by_key[k] for k in task.depends_on_json]
        if any(d.state=='failed' or d.state=='cancelled' for d in deps):
            task.state='cancelled'; task.error='Dependency did not succeed'; continue
        if not all(d.state=='succeeded' for d in deps): continue
        task.state='running'; task.attempts+=1; task.error=None; claimed.append(task)
    recalc(wf,tasks); await session.commit()
    return [TaskOut(id=t.id,key=t.key,kind=t.kind,payload=t.payload_json,depends_on=t.depends_on_json,state=t.state,attempts=t.attempts,max_attempts=t.max_attempts,result=t.result_json,error=t.error) for t in claimed]

@router.post('/{workflow_id}/tasks/{task_id}/succeed', response_model=WorkflowOut)
async def succeed_task(workflow_id: str, task_id: str, result: dict, user: User=Depends(current_user), session: AsyncSession=Depends(get_session)):
    wf,tasks=await load_workflow(workflow_id,user,session); task=next((t for t in tasks if t.id==task_id),None)
    if task is None: raise HTTPException(404,'Task not found')
    if task.state=='succeeded': return render(wf,tasks)
    if task.state!='running': raise HTTPException(409,'Only running tasks can succeed')
    task.state='succeeded'; task.result_json=result; task.error=None; recalc(wf,tasks); await session.commit(); return render(wf,tasks)

@router.post('/{workflow_id}/tasks/{task_id}/fail', response_model=WorkflowOut)
async def fail_task(workflow_id: str, task_id: str, body: dict, user: User=Depends(current_user), session: AsyncSession=Depends(get_session)):
    wf,tasks=await load_workflow(workflow_id,user,session); task=next((t for t in tasks if t.id==task_id),None)
    if task is None: raise HTTPException(404,'Task not found')
    if task.state!='running': raise HTTPException(409,'Only running tasks can fail')
    task.error=str(body.get('error','Task failed'))[:2000]
    task.state='pending' if task.attempts < task.max_attempts else 'failed'
    recalc(wf,tasks); await session.commit(); return render(wf,tasks)

@router.post('/{workflow_id}/cancel', response_model=WorkflowOut)
async def cancel_workflow(workflow_id: str, user: User=Depends(current_user), session: AsyncSession=Depends(get_session)):
    wf,tasks=await load_workflow(workflow_id,user,session)
    if wf.state in {'succeeded','failed','cancelled'}: raise HTTPException(409,'Workflow is terminal')
    for task in tasks:
        if task.state in {'pending','running'}: task.state='cancelled'; task.error='Workflow cancelled'
    wf.state='cancelled'; await session.commit(); return render(wf,tasks)
