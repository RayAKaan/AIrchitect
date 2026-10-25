from pydantic import BaseModel, Field

class PlanningRule(BaseModel):
    value: float | None = None
    unit: str
    source: str = "UNKNOWN"
    source_version: str | None = None
    effective_date: str | None = None
    applicability: str | None = None
    status: str = "UNKNOWN"

class EnvelopeRequest(BaseModel):
    setback_m: PlanningRule = Field(default_factory=lambda: PlanningRule(value=0, unit="m", source="USER_DESIGN_PARAMETER", status="DESIGN_PARAMETER"))
    max_coverage: PlanningRule | None = None
    far: PlanningRule | None = None
    max_height_m: PlanningRule | None = None

