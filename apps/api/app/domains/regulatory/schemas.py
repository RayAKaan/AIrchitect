from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

Operator = Literal['lte', 'lt', 'gte', 'gt', 'eq', 'in', 'exists']

class RegulatoryRule(BaseModel):
    rule_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=250)
    field: str = Field(min_length=1, max_length=200)
    operator: Operator
    threshold: Any = None
    unit: str | None = Field(default=None, max_length=40)
    source_name: str = Field(min_length=1, max_length=250)
    source_reference: str = Field(min_length=1, max_length=500)
    source_version: str = Field(min_length=1, max_length=100)
    effective_date: str | None = None
    @model_validator(mode='after')
    def threshold_required(self):
        if self.operator not in ('exists',) and self.threshold is None:
            raise ValueError('threshold is required for this operator')
        return self

class RegulatoryEvaluationRequest(BaseModel):
    project_id: str = Field(min_length=1)
    source_revision: int = Field(ge=1)
    jurisdiction: str = Field(min_length=1, max_length=150)
    ruleset_id: str = Field(min_length=1, max_length=100)
    ruleset_version: str = Field(min_length=1, max_length=100)
    rules: list[RegulatoryRule] = Field(min_length=1, max_length=500)
    facts: dict[str, Any]
    @model_validator(mode='after')
    def unique_rules(self):
        ids = [r.rule_id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError('rule_id values must be unique')
        return self

class RegulatoryRuleResult(BaseModel):
    rule_id: str
    title: str
    status: Literal['pass', 'fail', 'unknown']
    observed_value: Any = None
    threshold: Any = None
    unit: str | None = None
    source_name: str
    source_reference: str
    source_version: str
    reason: str

class RegulatoryEvaluationResponse(BaseModel):
    evaluation_id: str
    project_id: str
    source_revision: int
    jurisdiction: str
    ruleset_id: str
    ruleset_version: str
    results: list[RegulatoryRuleResult]
    summary: dict[str, int]
    status: Literal['preliminary_only'] = 'preliminary_only'
    disclaimer: str = 'Preliminary automated screening only; not legal advice, permit approval, or a substitute for authority review.'
