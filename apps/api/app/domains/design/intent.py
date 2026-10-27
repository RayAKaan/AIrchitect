from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RoomRequirement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    room_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    name: str = Field(min_length=1, max_length=120)
    target_area_m2: float = Field(gt=0, le=100_000)
    min_area_m2: float | None = Field(default=None, gt=0, le=100_000)
    max_area_m2: float | None = Field(default=None, gt=0, le=100_000)
    level_index: int = Field(default=0, ge=0, le=200)
    required: bool = True

    @model_validator(mode="after")
    def validate_area_bounds(self) -> RoomRequirement:
        if self.min_area_m2 is not None and self.max_area_m2 is not None and self.min_area_m2 > self.max_area_m2:
            raise ValueError("min_area_m2 cannot exceed max_area_m2")
        if self.min_area_m2 is not None and self.target_area_m2 < self.min_area_m2:
            raise ValueError("target_area_m2 must satisfy min_area_m2")
        if self.max_area_m2 is not None and self.target_area_m2 > self.max_area_m2:
            raise ValueError("target_area_m2 must satisfy max_area_m2")
        return self


class AdjacencyRequirement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    first_room_id: str = Field(min_length=1, max_length=80)
    second_room_id: str = Field(min_length=1, max_length=80)
    relationship: Literal["adjacent", "near", "separate"]
    priority: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def distinct_rooms(self) -> AdjacencyRequirement:
        if self.first_room_id == self.second_room_id:
            raise ValueError("adjacency requirement must reference two distinct rooms")
        return self


class DesignIntent(BaseModel):
    """Structured design request produced by Copilot before command compilation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: str = Field(min_length=1, max_length=120)
    site_id: str = Field(min_length=1, max_length=120)
    site_width_m: float = Field(gt=0, le=100_000)
    site_depth_m: float = Field(gt=0, le=100_000)
    floors: int = Field(default=1, ge=1, le=200)
    floor_to_floor_m: float = Field(default=3, gt=0, le=20)
    setback_front_m: float = Field(default=0, ge=0, le=100_000)
    setback_rear_m: float = Field(default=0, ge=0, le=100_000)
    setback_left_m: float = Field(default=0, ge=0, le=100_000)
    setback_right_m: float = Field(default=0, ge=0, le=100_000)
    rooms: tuple[RoomRequirement, ...] = Field(min_length=1, max_length=500)
    adjacencies: tuple[AdjacencyRequirement, ...] = Field(default=(), max_length=2_000)

    @model_validator(mode="after")
    def validate_design_intent(self) -> DesignIntent:
        room_ids = [room.room_id for room in self.rooms]
        if len(room_ids) != len(set(room_ids)):
            raise ValueError("room_id values must be unique")
        known = set(room_ids)
        for adjacency in self.adjacencies:
            if adjacency.first_room_id not in known or adjacency.second_room_id not in known:
                raise ValueError("adjacency references an unknown room")
        if self.setback_left_m + self.setback_right_m >= self.site_width_m:
            raise ValueError("side setbacks leave no positive buildable width")
        if self.setback_front_m + self.setback_rear_m >= self.site_depth_m:
            raise ValueError("front/rear setbacks leave no positive buildable depth")
        return self
