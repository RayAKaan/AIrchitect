from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Identifier = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")]
PositiveLength = Annotated[float, Field(gt=0, le=100_000)]
NonNegativeLength = Annotated[float, Field(ge=0, le=100_000)]


class Point3D(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    x: float = Field(ge=-100_000, le=100_000)
    y: float = Field(ge=-100_000, le=100_000)
    z: float = Field(ge=-100_000, le=100_000)


class ModelMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1"] = "1"
    units: Literal["m"] = "m"


class ModelElement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Identifier
    level_id: Identifier | None = None
    name: str = Field(min_length=1, max_length=200)


class Site(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Identifier
    width_m: PositiveLength
    depth_m: PositiveLength
    origin: Point3D = Point3D(x=0, y=0, z=0)


class Building(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Identifier
    name: str = Field(min_length=1, max_length=200)
    site_id: Identifier


class Level(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Identifier
    building_id: Identifier
    name: str = Field(min_length=1, max_length=200)
    elevation_m: float = Field(ge=-100_000, le=100_000)
    height_m: PositiveLength


class Space(ModelElement):
    element_type: Literal["space"] = "space"
    level_id: Identifier
    boundary: tuple[Point3D, ...] = Field(min_length=3, max_length=10_000)
    min_area_m2: NonNegativeLength = 0

    @model_validator(mode="after")
    def validate_boundary(self) -> Space:
        if len({(point.x, point.y) for point in self.boundary}) < 3:
            raise ValueError("space boundary must contain at least three distinct XY points")
        if any(point.z != self.boundary[0].z for point in self.boundary):
            raise ValueError("space boundary must be planar in Z")
        return self


class Wall(ModelElement):
    element_type: Literal["wall"] = "wall"
    start: Point3D
    end: Point3D
    thickness_m: PositiveLength
    height_m: PositiveLength
    space_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_segment(self) -> Wall:
        if self.start == self.end:
            raise ValueError("wall start and end points must differ")
        if self.start.z != self.end.z:
            raise ValueError("wall baseline must be horizontal in Z")
        return self


class Door(ModelElement):
    element_type: Literal["door"] = "door"
    level_id: Identifier
    host_wall_id: Identifier
    offset_m: NonNegativeLength
    width_m: PositiveLength
    height_m: PositiveLength
    sill_height_m: NonNegativeLength = 0


class Window(ModelElement):
    element_type: Literal["window"] = "window"
    level_id: Identifier
    host_wall_id: Identifier
    offset_m: NonNegativeLength
    width_m: PositiveLength
    height_m: PositiveLength
    sill_height_m: NonNegativeLength = 0


class Slab(ModelElement):
    element_type: Literal["slab"] = "slab"
    boundary: tuple[Point3D, ...] = Field(min_length=3, max_length=10_000)
    thickness_m: PositiveLength

    @model_validator(mode="after")
    def validate_boundary(self) -> Slab:
        if any(point.z != self.boundary[0].z for point in self.boundary):
            raise ValueError("slab boundary must be planar in Z")
        return self


class Stair(ModelElement):
    element_type: Literal["stair"] = "stair"
    level_id: Identifier
    lower_level_id: Identifier
    upper_level_id: Identifier
    width_m: PositiveLength
    riser_m: PositiveLength
    tread_m: PositiveLength
    riser_count: int = Field(ge=1, le=500)


class ArchitecturalModel(BaseModel):
    """Immutable-in-use canonical building model.

    Mutations are intentionally performed by the command layer rather than by
    modifying model instances. This keeps revisions deterministic and makes the
    model safe to hash, compare, audit, and use as a dependency source.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: Identifier
    revision: int = Field(ge=1)
    metadata: ModelMetadata = ModelMetadata()
    site: Site
    buildings: tuple[Building, ...] = ()
    levels: tuple[Level, ...] = ()
    spaces: tuple[Space, ...] = ()
    walls: tuple[Wall, ...] = ()
    doors: tuple[Door, ...] = ()
    windows: tuple[Window, ...] = ()
    slabs: tuple[Slab, ...] = ()
    stairs: tuple[Stair, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> ArchitecturalModel:
        ids = self._all_ids()
        if len(ids) != len(set(ids)):
            raise ValueError("model element IDs must be globally unique")

        building_ids = {item.id for item in self.buildings}
        level_ids = {item.id for item in self.levels}
        wall_ids = {item.id for item in self.walls}
        space_ids = {item.id for item in self.spaces}
        if any(item.site_id != self.site.id for item in self.buildings):
            raise ValueError("building references unknown site")
        if any(item.building_id not in building_ids for item in self.levels):
            raise ValueError("level references unknown building")
        for collection in (self.spaces, self.walls, self.doors, self.windows, self.slabs, self.stairs):
            if any(item.level_id is not None and item.level_id not in level_ids for item in collection):
                raise ValueError("element references unknown level")
        if any(item.host_wall_id not in wall_ids for item in (*self.doors, *self.windows)):
            raise ValueError("opening references unknown wall")
        if any(item_id not in space_ids for wall in self.walls for item_id in wall.space_ids):
            raise ValueError("wall references unknown space")
        if any(item.upper_level_id not in level_ids or item.lower_level_id not in level_ids for item in self.stairs):
            raise ValueError("stair references unknown level")
        return self

    def _all_ids(self) -> tuple[str, ...]:
        collections = (
            (self.site,),
            self.buildings,
            self.levels,
            self.spaces,
            self.walls,
            self.doors,
            self.windows,
            self.slabs,
            self.stairs,
        )
        return tuple(item.id for collection in collections for item in collection)
