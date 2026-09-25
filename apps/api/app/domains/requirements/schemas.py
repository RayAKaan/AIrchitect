from enum import StrEnum
from pydantic import BaseModel, Field

class RequirementCategory(StrEnum):
    SITE = "site"
    AREA = "area"
    FLOORS = "floors"
    HEIGHT = "height"
    BUDGET = "budget"
    PARKING = "parking"
    BUILDING_TYPE = "building_program"
    TIMELINE = "timeline"

class Requirement(BaseModel):
    category: RequirementCategory
    parameter: str
    value: str | float | int
    unit: str | None = None
    source_text: str
    source_type: str = "user_brief"
    confirmation_status: str = "unconfirmed"

class RequirementIssue(BaseModel):
    code: str
    severity: str
    message: str
    related_parameters: list[str] = Field(default_factory=list)

class RequirementAnalysisRequest(BaseModel):
    brief: str = Field(min_length=10, max_length=20000)

class RequirementAnalysisResponse(BaseModel):
    requirements: list[Requirement]
    missing_information: list[str]
    issues: list[RequirementIssue]
    extraction_method: str = "deterministic_pattern_v1"
    requires_user_confirmation: bool = True
