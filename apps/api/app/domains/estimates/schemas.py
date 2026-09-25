from typing import Literal
from pydantic import BaseModel, Field, model_validator

Unit = Literal['m2', 'm3', 'each', 'kg', 'floor']

class QuantityInput(BaseModel):
    code: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_.:-]+$')
    description: str = Field(min_length=1, max_length=240)
    quantity: float = Field(ge=0, le=1e12)
    unit: Unit
    source: str = Field(min_length=1, max_length=240)

class RateBand(BaseModel):
    low: float = Field(ge=0, le=1e12)
    base: float = Field(ge=0, le=1e12)
    high: float = Field(ge=0, le=1e12)
    currency: Literal['SAR'] = 'SAR'
    source: str = Field(min_length=1, max_length=240)
    rate_schedule_version: str = Field(min_length=1, max_length=80)

    @model_validator(mode='after')
    def ordered(self):
        if not self.low <= self.base <= self.high:
            raise ValueError('rate band must satisfy low <= base <= high')
        return self

class EstimateLineInput(BaseModel):
    quantity_code: str
    category: str = Field(min_length=1, max_length=100)
    rate: RateBand

class EstimateRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    source_revision: int = Field(ge=1)
    geometry_artifact_id: str = Field(min_length=1, max_length=120)
    geometry_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    quantities: list[QuantityInput] = Field(min_length=1, max_length=200)
    lines: list[EstimateLineInput] = Field(min_length=1, max_length=200)
    contingency_pct: float = Field(default=0, ge=0, le=100)

    @model_validator(mode='after')
    def validate_refs(self):
        codes = [q.code for q in self.quantities]
        if len(codes) != len(set(codes)):
            raise ValueError('quantity codes must be unique')
        known = set(codes)
        if any(line.quantity_code not in known for line in self.lines):
            raise ValueError('each estimate line must reference a supplied quantity code')
        return self

class EstimateLine(BaseModel):
    category: str
    quantity_code: str
    quantity: float
    unit: Unit
    rate_low_sar: float
    rate_base_sar: float
    rate_high_sar: float
    total_low_sar: float
    total_base_sar: float
    total_high_sar: float
    rate_source: str
    rate_schedule_version: str

class EstimateResponse(BaseModel):
    estimate_id: str
    project_id: str
    source_revision: int
    geometry_artifact_id: str
    geometry_sha256: str
    currency: Literal['SAR'] = 'SAR'
    subtotal_low_sar: float
    subtotal_base_sar: float
    subtotal_high_sar: float
    contingency_pct: float
    contingency_low_sar: float
    contingency_base_sar: float
    contingency_high_sar: float
    total_low_sar: float
    total_base_sar: float
    total_high_sar: float
    lines: list[EstimateLine]
    status: Literal['preliminary'] = 'preliminary'
    caveats: list[str]
