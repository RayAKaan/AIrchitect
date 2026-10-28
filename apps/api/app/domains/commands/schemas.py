from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


CommandMode = Literal["preview", "commit"]


class CommandEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1, max_length=128)
    type: str = Field(min_length=1, max_length=120)
    schema_version: int = Field(ge=1, le=100)
    project_id: str = Field(min_length=1, max_length=64)
    version_id: str = Field(min_length=1, max_length=64)
    base_revision_hash: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict, max_length=100)
    mode: CommandMode = "preview"
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("command_id", "type", "project_id", "version_id", "base_revision_hash", "idempotency_key", "reason")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class CommandPreview(BaseModel):
    command_id: str
    command_type: str
    accepted: bool
    executable: bool = False
    execution_blockers: list[str] = Field(default_factory=list)
    canonical_mutation: bool = False
    base_revision_hash: str
    impact: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class CommandResult(BaseModel):
    command_id: str
    command_type: str
    status: Literal["previewed", "committed", "replayed"]
    revision_hash: str
    canonical_mutation: bool
    impact: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CommandValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
