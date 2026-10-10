from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ReasonedRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_must_be_meaningful(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("reason must contain at least three non-whitespace characters")
        return value


class SemanticPropertyEdit(ReasonedRequest):
    property: str = Field(min_length=1, max_length=80)
    value: Any
    expected_revision: int = Field(ge=1)


class SemanticLockChange(ReasonedRequest):
    expected_revision: int = Field(ge=1)


class SemanticElementCreate(ReasonedRequest):
    element_type: Literal["Space", "Wall", "Slab", "Roof", "Door", "Window"]
    name: str = Field(min_length=1, max_length=120)
    properties: dict[str, Any] = Field(default_factory=dict, max_length=30)
    level_number: int | None = Field(default=None, ge=1, le=300)
    host_element_id: str | None = Field(default=None, max_length=36)
    expected_revision: int = Field(ge=1)


class SemanticElementDelete(ReasonedRequest):
    expected_revision: int = Field(ge=1)


class SemanticHistoryAction(BaseModel):
    expected_revision: int = Field(ge=1)


class SemanticRegenerationRequest(BaseModel):
    element_ids: list[str] = Field(default_factory=list, max_length=5000)
    expected_world_model_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

class SemanticHostChange(ReasonedRequest):
    host_element_id: str | None = Field(default=None, max_length=36)
    expected_revision: int = Field(ge=1)
