from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class StageInput:
    """Immutable canonical input presented to one feasibility stage."""

    stage: str
    workflow_id: str
    project_version_id: str
    source_revision_hash: str
    payload: dict[str, Any]
    input_hash: str

    @classmethod
    def create(
        cls,
        *,
        stage: str,
        workflow_id: str,
        project_version_id: str,
        source_revision_hash: str,
        payload: Mapping[str, Any],
    ) -> StageInput:
        _require_identity(stage, "stage")
        _require_identity(workflow_id, "workflow_id")
        _require_identity(project_version_id, "project_version_id")
        _require_identity(source_revision_hash, "source_revision_hash")
        canonical_payload = dict(payload)
        return cls(
            stage=stage,
            workflow_id=workflow_id,
            project_version_id=project_version_id,
            source_revision_hash=source_revision_hash,
            payload=canonical_payload,
            input_hash=_canonical_hash(canonical_payload),
        )


@dataclass(frozen=True)
class StageOutput:
    stage: str
    source_revision_hash: str
    payload: dict[str, Any]
    output_hash: str
    engine_version: str

    @classmethod
    def create(
        cls,
        *,
        stage: str,
        source_revision_hash: str,
        payload: Mapping[str, Any],
        engine_version: str,
    ) -> StageOutput:
        _require_identity(stage, "stage")
        _require_identity(source_revision_hash, "source_revision_hash")
        _require_identity(engine_version, "engine_version")
        canonical_payload = dict(payload)
        return cls(
            stage=stage,
            source_revision_hash=source_revision_hash,
            payload=canonical_payload,
            output_hash=_canonical_hash(canonical_payload),
            engine_version=engine_version,
        )


StageHandler = Callable[[AsyncSession, StageInput], Awaitable[StageOutput]]


class PipelineStageRegistry:
    """Explicit stage registry with fail-closed lookup and output validation."""

    def __init__(self, handlers: Mapping[str, StageHandler] | None = None) -> None:
        self._handlers = dict(handlers or {})

    def register(self, stage: str, handler: StageHandler) -> None:
        _require_identity(stage, "stage")
        if stage in self._handlers:
            raise ValueError(f"stage handler already registered: {stage}")
        self._handlers[stage] = handler

    def get(self, stage: str) -> StageHandler:
        handler = self._handlers.get(stage)
        if handler is None:
            raise ValueError(f"no pipeline stage handler registered for {stage}")
        return handler

    async def execute(
        self, session: AsyncSession, stage_input: StageInput
    ) -> StageOutput:
        output = await self.get(stage_input.stage)(session, stage_input)
        validate_stage_output(stage_input, output)
        return output


def validate_stage_output(stage_input: StageInput, output: StageOutput) -> None:
    if output.stage != stage_input.stage:
        raise ValueError("pipeline stage handler changed stage identity")
    if output.source_revision_hash != stage_input.source_revision_hash:
        raise ValueError("pipeline stage handler changed source revision identity")
    if output.output_hash != _canonical_hash(output.payload):
        raise ValueError("pipeline stage handler returned an invalid output hash")


def _require_identity(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
