from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Quantity(BaseModel):
    value: float
    unit: Literal["m", "m2", "count", "degree"]


class ValueProvenance(BaseModel):
    source_type: Literal["USER_BRIEF", "DOCUMENT", "SYSTEM_ASSUMPTION", "HUMAN_REVIEW", "DERIVED"]
    source_id: str
    confirmed: bool = False


class Location(BaseModel):
    city: str | None = None
    region: str | None = None
    country: str = "Saudi Arabia"


class Site(BaseModel):
    location: Location = Field(default_factory=Location)
    area: Quantity | None = None
    width: Quantity | None = None
    depth: Quantity | None = None
    boundary: list[tuple[float, float]] | None = None
    orientation: Quantity | None = None


class Level(BaseModel):
    level_number: int
    name: str
    elevation: Quantity | None = None
    floor_to_floor_height: Quantity | None = None
    area: Quantity | None = None


class Space(BaseModel):
    id: str
    name: str
    use: str
    level_number: int | None = None
    area: Quantity | None = None


class Parking(BaseModel):
    arrangement: str | None = None
    spaces: Quantity | None = None


class StructuralGrid(BaseModel):
    system: str | None = None
    x_spacings_m: list[float] = Field(default_factory=list)
    y_spacings_m: list[float] = Field(default_factory=list)


class Building(BaseModel):
    use: str | None = None
    floor_count: int | None = Field(default=None, ge=1)
    floor_to_floor_height: Quantity | None = None
    height: Quantity | None = None
    target_gfa: Quantity | None = None
    coverage: float | None = Field(default=None, ge=0, le=1)


class BuildingWorldModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1.0.0"
    project_id: str
    project_version_id: str
    site: Site = Field(default_factory=Site)
    building: Building = Field(default_factory=Building)
    levels: list[Level] = Field(default_factory=list)
    spaces: list[Space] = Field(default_factory=list)
    parking: Parking = Field(default_factory=Parking)
    structural_grid: StructuralGrid = Field(default_factory=StructuralGrid)
    properties: dict[str, Any] = Field(default_factory=dict)
    requirement_ids: list[str] = Field(default_factory=list)
    assumption_ids: list[str] = Field(default_factory=list)
    provenance: dict[str, ValueProvenance] = Field(default_factory=dict)
    unknowns: list[str] = Field(default_factory=list)
    consistency_issues: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_quantities(self):
        positive = [self.site.area, self.site.width, self.site.depth, self.building.floor_to_floor_height]
        if any(q is not None and q.value <= 0 for q in positive):
            raise ValueError("site dimensions/area and floor-to-floor height must be positive")
        if self.building.target_gfa is not None and self.building.target_gfa.value < 0:
            raise ValueError("target GFA cannot be negative")
        if self.building.height is not None and self.building.height.value < 0:
            raise ValueError("building height cannot be negative")
        level_numbers = [level.level_number for level in self.levels]
        if len(level_numbers) != len(set(level_numbers)):
            raise ValueError("level numbers must be unique")
        return self
