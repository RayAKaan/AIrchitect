from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Evidence(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=128)
    source_type: Literal['document','calculation','rule','review','measurement','other']
    source_ref: str = Field(min_length=1, max_length=512)
    version: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=1000)
    verified: bool = False

class ValidationCheck(BaseModel):
    check_id: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=100)
    status: Literal['passed','failed','unknown','not_applicable']
    message: str = Field(min_length=1, max_length=2000)
    required: bool = True
    evidence_ids: list[str] = Field(default_factory=list)
    requires_human_review: bool = False

class ValidationRequest(BaseModel):
    project_id: str
    artifact_id: str = Field(min_length=1, max_length=128)
    artifact_version: str = Field(min_length=1, max_length=128)
    source_hash: str = Field(min_length=1, max_length=256)
    current_source_hash: str = Field(min_length=1, max_length=256)
    checks: list[ValidationCheck] = Field(min_length=1, max_length=500)
    evidence: list[Evidence] = Field(default_factory=list, max_length=1000)
    declared_current: bool = True

    @model_validator(mode='after')
    def unique_ids(self):
        ids=[c.check_id for c in self.checks]
        if len(ids)!=len(set(ids)): raise ValueError('check_id values must be unique')
        eids=[e.evidence_id for e in self.evidence]
        if len(eids)!=len(set(eids)): raise ValueError('evidence_id values must be unique')
        return self

class ValidationResponse(BaseModel):
    artifact_id: str
    artifact_version: str
    status: Literal['ready_for_review','blocked','stale','incomplete']
    current: bool
    passed: int
    failed: int
    unknown: int
    missing_evidence: list[str]
    human_review_required: bool
    checks: list[ValidationCheck]
    evidence: list[Evidence]
    limitations: list[str]
