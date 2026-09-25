import pytest
from pydantic import ValidationError
from app.domains.workflows.schemas import WorkflowCreate

def valid(**overrides):
    data = {'project_id':'p1','workflow_type':'feasibility','idempotency_key':'request-00001',
            'tasks':[{'key':'intake','kind':'normalize'}, {'key':'geometry','kind':'massing','depends_on':['intake']} ]}
    data.update(overrides)
    return data

def test_accepts_valid_dag():
    body=WorkflowCreate(**valid())
    assert len(body.tasks)==2

def test_rejects_duplicate_task_keys():
    data=valid(tasks=[{'key':'a','kind':'x'},{'key':'a','kind':'y'}])
    with pytest.raises(ValidationError): WorkflowCreate(**data)

def test_rejects_unknown_dependency():
    data=valid(tasks=[{'key':'a','kind':'x','depends_on':['missing']}])
    with pytest.raises(ValidationError): WorkflowCreate(**data)

def test_rejects_cycle():
    data=valid(tasks=[{'key':'a','kind':'x','depends_on':['b']},{'key':'b','kind':'x','depends_on':['a']}])
    with pytest.raises(ValidationError): WorkflowCreate(**data)

def test_rejects_self_dependency():
    data=valid(tasks=[{'key':'a','kind':'x','depends_on':['a']}])
    with pytest.raises(ValidationError): WorkflowCreate(**data)
