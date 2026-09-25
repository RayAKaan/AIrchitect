from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class Provenance(BaseModel):
    source_type: Literal['user', 'document', 'derived', 'model', 'system'] = 'user'
    source_reference: str | None = None
    source_version: str | None = None
    user_confirmed: bool = False
    calculation_method: str | None = None
    model_provider: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    validation_status: Literal['unvalidated', 'valid', 'invalid', 'unknown'] = 'unvalidated'

class Dimension(BaseModel):
    value: float = Field(gt=0)
    unit: Literal['m', 'ft'] = 'm'

class SiteModel(BaseModel):
    area: Dimension | None = None
    boundary: list[tuple[float, float]] = Field(default_factory=list)
    address: str | None = None
    jurisdiction: str = 'Saudi Arabia'
    provenance: Provenance = Field(default_factory=Provenance)

class BuildingLevel(BaseModel):
    level_id: str
    name: str
    elevation: float = 0
    floor_to_floor_height: Dimension = Field(default_factory=lambda: Dimension(value=3.6))
    provenance: Provenance = Field(default_factory=Provenance)

class BuildingSpace(BaseModel):
    space_id: str
    name: str
    level_id: str
    area: Dimension
    space_type: str = 'unspecified'
    provenance: Provenance = Field(default_factory=Provenance)

class StructuralGrid(BaseModel):
    x_spacings: list[float] = Field(default_factory=list)
    y_spacings: list[float] = Field(default_factory=list)
    system: str = 'unspecified'
    provenance: Provenance = Field(default_factory=Provenance)

class BuildingModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: str = '1.0.0'
    site: SiteModel = Field(default_factory=SiteModel)
    levels: list[BuildingLevel] = Field(default_factory=list)
    spaces: list[BuildingSpace] = Field(default_factory=list)
    structural_grid: StructuralGrid = Field(default_factory=StructuralGrid)
    properties: dict[str, object] = Field(default_factory=dict)
    provenance: dict[str, Provenance] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_references(self):
        level_ids = [level.level_id for level in self.levels]
        if len(level_ids) != len(set(level_ids)):
            raise ValueError('level_id values must be unique')
        space_ids = [space.space_id for space in self.spaces]
        if len(space_ids) != len(set(space_ids)):
            raise ValueError('space_id values must be unique')
        unknown = sorted({s.level_id for s in self.spaces} - set(level_ids))
        if unknown:
            raise ValueError(f'spaces reference unknown levels: {unknown}')
        if any(v <= 0 for v in self.structural_grid.x_spacings + self.structural_grid.y_spacings):
            raise ValueError('structural grid spacings must be positive')
        return self

class WorldModelRevisionOut(BaseModel):
    id: str
    project_id: str
    revision: int
    model: BuildingModel
    created_by: str
    created_at: str

class WorldModelMutation(BaseModel):
    model: BuildingModel
    expected_project_version: int = Field(ge=1)
