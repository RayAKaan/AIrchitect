from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domains.geometry.engine import generate as generate_geometry
from app.domains.geometry.schemas import GeometryGenerateRequest


@dataclass(frozen=True)
class RegenerationInput:
    artifact_type: str
    source_revision_hash: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class RegenerationOutput:
    artifact_type: str
    source_revision_hash: str
    payload: dict[str, Any]
    output_hash: str
    engine_version: str


Handler = Callable[[RegenerationInput], RegenerationOutput]


def _content_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _geometry_handler(request: RegenerationInput) -> RegenerationOutput:
    raw_request = request.payload.get("regeneration_request")
    if not isinstance(raw_request, dict):
        raise ValueError("geometry artifact is missing regeneration_request")
    geometry_request = GeometryGenerateRequest.model_validate(raw_request)
    artifacts = generate_geometry(geometry_request)
    payload = {
        "project_id": geometry_request.project_id,
        "source_revision": geometry_request.source_revision,
        "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
    }
    return RegenerationOutput(
        artifact_type=request.artifact_type,
        source_revision_hash=request.source_revision_hash,
        payload=payload,
        output_hash=_content_hash(payload),
        engine_version="geometry-engine-v1",
    )


class RegenerationHandlerRegistry:
    """Explicit registry; unsupported artifact types fail closed."""

    def __init__(self, handlers: dict[str, Handler] | None = None) -> None:
        self._handlers = {"geometry": _geometry_handler, **(handlers or {})}

    def execute(self, request: RegenerationInput) -> RegenerationOutput:
        handler = self._handlers.get(request.artifact_type)
        if handler is None:
            raise ValueError(f"no regeneration handler registered for {request.artifact_type}")
        output = handler(request)
        if output.source_revision_hash != request.source_revision_hash:
            raise ValueError("regeneration handler changed source revision identity")
        return output
