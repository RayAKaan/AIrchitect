from typing import Any
from pydantic import BaseModel, Field, model_validator

class DecisionRequest(BaseModel):
    decision_id: str | None = None
    decision_type: str = Field(min_length=1, max_length=100)
    context: dict[str, Any] = Field(default_factory=dict)
    allowed_options: list[str] = Field(min_length=1)
    constraints: dict[str, Any] = Field(default_factory=dict)
    project_version_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_options(self):
        if len(set(self.allowed_options)) != len(self.allowed_options):
            raise ValueError("allowed_options must be unique")
        return self

class DecisionResponse(BaseModel):
    decision_id: str
    selected_option: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    rationale: str
    provider: str
    provider_version: str
    validation_status: str
    fallback_used: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
