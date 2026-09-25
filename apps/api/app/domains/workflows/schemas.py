from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

TaskState = Literal['pending','running','succeeded','failed','cancelled']

class TaskSpec(BaseModel):
    key: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_.:-]+$')
    kind: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    max_attempts: int = Field(default=3, ge=1, le=10)

class WorkflowCreate(BaseModel):
    project_id: str
    workflow_type: str = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=200)
    tasks: list[TaskSpec] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def validate_dag(self):
        keys = [t.key for t in self.tasks]
        if len(keys) != len(set(keys)):
            raise ValueError('Task keys must be unique')
        known = set(keys)
        for task in self.tasks:
            if len(task.depends_on) != len(set(task.depends_on)):
                raise ValueError(f'Duplicate dependencies in task {task.key}')
            if task.key in task.depends_on or not set(task.depends_on) <= known:
                raise ValueError(f'Invalid dependency in task {task.key}')
        graph = {t.key: set(t.depends_on) for t in self.tasks}
        visited: set[str] = set()
        active: set[str] = set()
        def visit(key: str):
            if key in active: raise ValueError('Workflow task graph contains a cycle')
            if key in visited: return
            active.add(key)
            for dep in graph[key]: visit(dep)
            active.remove(key); visited.add(key)
        for key in graph: visit(key)
        return self

class TaskOut(BaseModel):
    id: str
    key: str
    kind: str
    payload: dict[str, Any]
    depends_on: list[str]
    state: TaskState
    attempts: int
    max_attempts: int
    result: dict[str, Any] | None
    error: str | None

class WorkflowOut(BaseModel):
    id: str
    project_id: str
    workflow_type: str
    state: str
    tasks: list[TaskOut]
    created_at: datetime
