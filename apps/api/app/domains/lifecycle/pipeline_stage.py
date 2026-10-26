from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
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
        payload: dict[str, Any],
    ) -> StageInput:
        if not stage.strip():
            raise ValueError("stage must not be empty")
        if not source_revision_hash:
            raise ValueError("source_revision_hash must not be empty")
        canonical = _canonical_hash(payload)
        return cls(stage, workflow_id, project_version_id, source_revision_hash, dict(payload), canonical)


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
        payload: dict[str, Any],
        engine_version: str,
    ) -> StageOutput:
        if not stage.strip():
            raise ValueError("stage must not be empty")
        if not engine_version.strip():
            raise ValueError("engine_version must not be empty")
        return cls(stage, source_revision_hash, dict(payload), _canonical_hash(payload), engine_version)


StageHandler = Callable[[AsyncSession, StageInput], Awaitable[StageOutput]]


class PipelineStageRegistry:
    """Explicit stage registry with fail-closed lookup and output validation."""

    def __init__(self, handlers: dict[str, StageHandler] | None = None) -> None:
        self._handlers = dict(handlers or {})

    def register(self, stage: str, handler: StageHandler) -> None:
        normalized = stage.strip()
        if not normalized:
            raise ValueError("stage must not be empty")
        if normalized in self._handlers:
            raise ValueError(f"stage handler already registered: {normalized}")
        self._handlers[normalized] = handler

    def get(self, stage: str) -> StageHandler:
        handler = self._handlers.get(stage)
        if handler is None:
            raise ValueError(f"no pipeline stage handler registered for {stage}")
        return handler

    async def execute(self, session: AsyncSession, stage_input: StageInput) -> StageOutput:
        output = await self.get(stage_input.stage)(session, stage_input)
        if output.stage != stage_input.stage:
            raise ValueError("pipeline stage handler changed stage identity")
        if output.source_revision_hash != stage_input.source_revision_hash:
            raise ValueError("pipeline stage handler changed source revision identity")
        if output.output_hash != _canonical_hash(output.payload):
            raise ValueError("pipeline stage handler returned an invalid output hash")
        return output


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
