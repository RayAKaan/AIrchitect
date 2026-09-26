from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Project, WorkflowRecord, WorkflowTaskRecord, User
from app.db.session import get_session
from app.dependencies import current_user, require_membership
from .schemas import WorkflowCreate, WorkflowOut, TaskOut
from pydantic import BaseModel
from app.domains.foundation.service import resolve_project_version
from .feasibility import STEPS, create_run, execute_run

router = APIRouter(tags=['workflows'])

class FeasibilityRunCreate(BaseModel):
    version_ref: str
    rate_schedule_id: str | None = None

@router.post('/projects/{project_id}/workflows/feasibility',status_code=201)
async def start_feasibility(project_id:str,body:FeasibilityRunCreate,idempotency_key:str=Header(alias='Idempotency-Key',min_length=8,max_length=200),user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    project,version=await resolve_project_version(session,project_id,body.version_ref,user.id,write=True)
    wf=await create_run(session,project,version,user,idempotency_key,body.rate_schedule_id)
    wf=await execute_run(session,wf,user)
    tasks=list((await session.scalars(select(WorkflowTaskRecord).where(WorkflowTaskRecord.workflow_id==wf.id))).all())
    return feasibility_out(wf,tasks)

@router.get('/projects/{project_id}/workflows')
async def list_project_workflows(project_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    project=await session.get(Project,project_id)
    if project is None:raise HTTPException(404,'Project not found')
    await require_membership(project.organization_id,user,session)
    rows=(await session.scalars(select(WorkflowRecord).where(WorkflowRecord.project_id==project.id).order_by(WorkflowRecord.created_at.desc()))).all()
    return {'workflows':[feasibility_out(x,[]) for x in rows]}

def feasibility_out(wf,tasks):
    return {'id':wf.id,'project_id':wf.project_id,'project_version_id':wf.project_version_id,'workflow_type':wf.workflow_type,'state':wf.state,'current_step':wf.current_step,'input_hash':wf.input_hash,'workflow_definition_version':wf.workflow_definition_version,'failure':{'class':wf.failure_class,'code':wf.failure_code,'message':wf.failure_message} if wf.failure_code else None,'metadata':wf.metadata_json,'created_at':wf.created_at,'started_at':wf.started_at,'completed_at':wf.completed_at,'steps':[{'id':t.id,'key':t.key,'state':t.state,'attempts':t.attempts,'max_attempts':t.max_attempts,'input_hash':t.input_hash,'output_hash':t.output_hash,'result':t.result_json,'failure_class':t.failure_class,'error_code':t.error_code,'error_message':t.error_message,'started_at':t.started_at,'completed_at':t.completed_at} for t in sorted(tasks,key=lambda x:STEPS.index(x.key) if x.key in STEPS else len(STEPS))]}


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
    elif any(s == 'blocked' for s in states): wf.state = 'blocked'
    elif any(s == 'stale' for s in states): wf.state = 'stale'
    elif all(s == 'cancelled' for s in states): wf.state = 'cancelled'
    else: wf.state = 'pending'

@router.post('/workflows', response_model=WorkflowOut, status_code=201)
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

@router.get('/workflows/{workflow_id}')
async def get_workflow(workflow_id: str, user: User=Depends(current_user), session: AsyncSession=Depends(get_session)):
    wf,tasks=await load_workflow(workflow_id,user,session)
    return feasibility_out(wf,tasks) if wf.workflow_type=='FEASIBILITY_V1' else render(wf,tasks)

@router.post('/workflows/{workflow_id}/resume')
async def resume_workflow(workflow_id:str,user:User=Depends(current_user),session:AsyncSession=Depends(get_session)):
    wf,tasks=await load_workflow(workflow_id,user,session)
    if wf.workflow_type!='FEASIBILITY_V1':raise HTTPException(409,'Only feasibility workflows use this resume operation')
    if wf.state=='FAILED' and wf.failure_class=='RETRYABLE':
        failed=next((x for x in tasks if x.state=='FAILED'),None)
        if failed and failed.attempts<failed.max_attempts:failed.state='PENDING';failed.error=None;failed.error_code=None;failed.error_message=None;wf.state='RUNNING';wf.failure_class=None;wf.failure_code=None;wf.failure_message=None;await session.commit()
    wf=await execute_run(session,wf,user);tasks=list((await session.scalars(select(WorkflowTaskRecord).where(WorkflowTaskRecord.workflow_id==wf.id))).all());return feasibility_out(wf,tasks)

@router.post('/workflows/{workflow_id}/claim', response_model=list[TaskOut])
async def claim_ready(workflow_id: str, worker_id: str = 'api-worker', lease_seconds: int = 60,
    user: User=Depends(current_user), session: AsyncSession=Depends(get_session)):
    """Atomically claim ready work. PostgreSQL uses SKIP LOCKED; expired leases are reclaimable."""
    wf = await session.scalar(select(WorkflowRecord).where(WorkflowRecord.id == workflow_id).with_for_update())
    if wf is None: raise HTTPException(404, 'Workflow not found')
    await require_membership(wf.organization_id, user, session)
    if wf.state in {'cancelled','succeeded','failed'}: return []
    now = datetime.now(timezone.utc)
    tasks = list((await session.scalars(select(WorkflowTaskRecord).where(
        WorkflowTaskRecord.workflow_id == workflow_id,
        or_(WorkflowTaskRecord.state == 'pending',
            (WorkflowTaskRecord.state == 'running') & (WorkflowTaskRecord.lease_expires_at < now)),
        WorkflowTaskRecord.available_at <= now).order_by(WorkflowTaskRecord.key).with_for_update(skip_locked=True))).all())
    all_tasks = list((await session.scalars(select(WorkflowTaskRecord).where(WorkflowTaskRecord.workflow_id == workflow_id))).all())
    by_key={t.key:t for t in all_tasks}; claimed=[]
    for task in tasks:
        deps=[by_key[k] for k in task.depends_on_json]
        if any(d.state in {'failed','cancelled','blocked'} for d in deps):
            task.state='blocked'; task.error='Dependency did not succeed'; continue
        if not all(d.state=='succeeded' for d in deps): continue
        task.state='running'; task.attempts+=1; task.error=None; task.owner=worker_id
        task.heartbeat_at=now; task.lease_expires_at=now+timedelta(seconds=max(10,min(lease_seconds,3600))); claimed.append(task)
    recalc(wf,all_tasks); await session.commit()
    return [TaskOut(id=t.id,key=t.key,kind=t.kind,payload=t.payload_json,depends_on=t.depends_on_json,state=t.state,attempts=t.attempts,max_attempts=t.max_attempts,result=t.result_json,error=t.error) for t in claimed]

@router.post('/workflows/{workflow_id}/tasks/{task_id}/succeed', response_model=WorkflowOut)
async def succeed_task(workflow_id: str, task_id: str, result: dict, user: User=Depends(current_user), session: AsyncSession=Depends(get_session)):
    wf,tasks=await load_workflow(workflow_id,user,session); task=next((t for t in tasks if t.id==task_id),None)
    if task is None: raise HTTPException(404,'Task not found')
    if task.state=='succeeded': return render(wf,tasks)
    if task.state!='running': raise HTTPException(409,'Only running tasks can succeed')
    task.state='succeeded'; task.result_json=result; task.error=None; task.owner=None; task.lease_expires_at=None
    recalc(wf,tasks); await session.commit(); return render(wf,tasks)

@router.post('/workflows/{workflow_id}/tasks/{task_id}/fail', response_model=WorkflowOut)
async def fail_task(workflow_id: str, task_id: str, body: dict, user: User=Depends(current_user), session: AsyncSession=Depends(get_session)):
    wf,tasks=await load_workflow(workflow_id,user,session); task=next((t for t in tasks if t.id==task_id),None)
    if task is None: raise HTTPException(404,'Task not found')
    if task.state!='running': raise HTTPException(409,'Only running tasks can fail')
    task.error=str(body.get('error','Task failed'))[:2000]
    task.owner=None; task.lease_expires_at=None
    if task.attempts < task.max_attempts:
        task.state='pending'; task.available_at=datetime.now(timezone.utc)+timedelta(seconds=min(300, 2 ** task.attempts))
    else: task.state='failed'
    recalc(wf,tasks); await session.commit(); return render(wf,tasks)

@router.post('/workflows/{workflow_id}/cancel', response_model=WorkflowOut)
async def cancel_workflow(workflow_id: str, user: User=Depends(current_user), session: AsyncSession=Depends(get_session)):
    wf,tasks=await load_workflow(workflow_id,user,session)
    if wf.state in {'succeeded','failed','cancelled','COMPLETED','CANCELLED','BLOCKED'}: raise HTTPException(409,'Workflow is terminal')
    phase4=wf.workflow_type=='FEASIBILITY_V1'
    for task in tasks:
        if task.state in {'pending','running','PENDING','RUNNING'}: task.state='CANCELLED' if phase4 else 'cancelled'; task.error='Workflow cancelled';task.error_message='Workflow cancelled';task.completed_at=datetime.now(timezone.utc)
    wf.state='CANCELLED' if phase4 else 'cancelled';wf.completed_at=datetime.now(timezone.utc); await session.commit()
    return feasibility_out(wf,tasks) if phase4 else render(wf,tasks)
