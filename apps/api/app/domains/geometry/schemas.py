from typing import Literal
from pydantic import BaseModel, Field, model_validator

class MassingOption(BaseModel):
    option_id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_.:-]+$')
    floors: int = Field(ge=1, le=200)
    floor_to_floor_m: float = Field(default=3.6, gt=0, le=20)
    setback_m: float = Field(default=0, ge=0, le=10000)

class GeometryGenerateRequest(BaseModel):
    project_id: str
    source_revision: int = Field(ge=1)
    footprint_width_m: float = Field(gt=0, le=10000)
    footprint_depth_m: float = Field(gt=0, le=10000)
    options: list[MassingOption] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def unique_options(self):
        ids = [o.option_id for o in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError('option_id values must be unique')
        for option in self.options:
            if option.setback_m * 2 >= min(self.footprint_width_m, self.footprint_depth_m):
                raise ValueError(f'setback leaves no positive footprint for option {option.option_id}')
        return self

class GeometryArtifact(BaseModel):
    artifact_id: str
    option_id: str
    source_revision: int
    units: Literal['m'] = 'm'
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, ...]]
    footprint_area_m2: float
    gross_floor_area_m2: float
    gross_volume_m3: float
    height_m: float
    geometry_sha256: str
    validation: dict[str, str | bool]

class GeometryGenerateResponse(BaseModel):
    project_id: str
    source_revision: int
    artifacts: list[GeometryArtifact]
    caveats: list[str]
