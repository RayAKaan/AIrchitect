from typing import Any, Literal
from pydantic import BaseModel, Field


class BriefIn(BaseModel):
    text: str = Field(min_length=3, max_length=20000)
    source_reference: str | None = Field(default=None, max_length=500)
    expected_revision: int = Field(ge=1)


class RequirementEdit(BaseModel):
    value: Any
    unit: str | None = Field(default=None, max_length=40)
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


class RequirementDecision(BaseModel):
    decision: Literal["CONFIRMED", "REJECTED"]
    expected_revision: int = Field(ge=1)


class AssumptionIn(BaseModel):
    parameter: str = Field(min_length=1, max_length=120)
    value: Any
    unit: str | None = Field(default=None, max_length=40)
    reason: str = Field(min_length=3, max_length=2000)
    source: str = Field(default="USER", max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    impact_scope: list[str] = Field(default_factory=list, max_length=30)
    expected_revision: int = Field(ge=1)


class AssumptionPatch(BaseModel):
    status: Literal["accepted", "rejected"] | None = None
    value: Any | None = None
    reason: str | None = Field(default=None, min_length=3, max_length=2000)
    expected_revision: int = Field(ge=1)


class VersionCreate(BaseModel):
    expected_current_version_id: str
    expected_revision: int = Field(ge=1)
    change_summary: str = Field(min_length=3, max_length=1000)
    changes: dict[str, Any] = Field(default_factory=dict, max_length=50)


class WorldModelCommit(BaseModel):
    expected_revision: int = Field(ge=1)
    commit: bool = True
