from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

AssumptionStatus = Literal['proposed', 'accepted', 'rejected', 'replaced']

class AssumptionCreate(BaseModel):
    parameter: str = Field(min_length=1, max_length=120)
    value: Any
    unit: str | None = Field(default=None, max_length=40)
    reason: str = Field(min_length=1, max_length=2000)
    source: str = Field(default='system-proposed', max_length=500)
    impact_scope: list[str] = Field(default_factory=list, max_length=30)
    confidence: float | None = Field(default=None, ge=0, le=1)

class AssumptionOut(BaseModel):
    id: str
    project_id: str
    project_version: int
    parameter: str
    value: Any
    unit: str | None
    reason: str
    source: str
    status: AssumptionStatus
    impact_scope: list[str]
    confidence: float | None
    created_by: str
    created_at: datetime
    supersedes_id: str | None

class AssumptionTransition(BaseModel):
    status: Literal['accepted', 'rejected']

class AssumptionReplace(BaseModel):
    replacement: AssumptionCreate
