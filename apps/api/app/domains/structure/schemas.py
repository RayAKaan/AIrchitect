from typing import Literal
from pydantic import BaseModel, Field, model_validator


class StructuralConceptRequest(BaseModel):
    project_id: str = Field(min_length=1)
    geometry_artifact_id: str = Field(min_length=1)
    geometry_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_revision: int = Field(ge=1)
    footprint_width_m: float = Field(gt=0, le=1000)
    footprint_depth_m: float = Field(gt=0, le=1000)
    floors: int = Field(ge=1, le=100)
    floor_to_floor_m: float = Field(gt=0, le=20)
    preferred_max_bay_m: float = Field(default=8.0, gt=0, le=20)
    system: Literal['reinforced_concrete_frame', 'steel_frame', 'unknown'] = 'unknown'
    imposed_load_kpa: float | None = Field(default=None, gt=0, le=100)
    soil_report_available: bool = False

    @model_validator(mode='after')
    def reasonable_bounds(self):
        if self.footprint_width_m > 1000 or self.footprint_depth_m > 1000:
            raise ValueError('Footprint exceeds conceptual engine bounds')
        return self


class StructuralConceptResponse(BaseModel):
    concept_id: str
    project_id: str
    geometry_artifact_id: str
    geometry_sha256: str
    source_revision: int
    system: str
    grid: dict[str, list[float] | int | float]
    preliminary_quantities: dict[str, int | float | str]
    input_completeness: dict[str, bool]
    checks: dict[str, str | bool]
    limitations: list[str]
    status: Literal['concept_only'] = 'concept_only'
