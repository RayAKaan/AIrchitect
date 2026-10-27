from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ElementType = Literal[
    "site",
    "building",
    "level",
    "space",
    "wall",
    "door",
    "window",
    "slab",
    "stair",
]
Operation = Literal["create", "update", "delete"]


class ModelCommand(BaseModel):
    """Validated, revision-anchored mutation intent for the canonical model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    command_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    operation: Operation
    element_type: ElementType
    element_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    expected_revision: int = Field(ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload_shape(self) -> ModelCommand:
        if self.operation == "delete" and self.payload:
            raise ValueError("delete commands cannot carry a payload")
        if self.operation == "create" and not self.payload:
            raise ValueError("create commands require a payload")
        return self


def canonical_command_payload(command: ModelCommand) -> dict[str, Any]:
    """Return the stable representation used for fingerprints and audit records."""
    return command.model_dump(mode="json", exclude_none=False)


def command_fingerprint(command: ModelCommand) -> str:
    encoded = json.dumps(
        canonical_command_payload(command),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
