from __future__ import annotations

import contextvars
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


_CONTEXT: contextvars.ContextVar["ObservabilityContext"] = contextvars.ContextVar(
    "observability_context",
    default=None,  # type: ignore[arg-type]
)


@dataclass(slots=True)
class ObservabilityContext:
    request_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str | None = None
    revision_id: str | None = None
    command_id: str | None = None
    generation_id: str | None = None
    actor_id: str | None = None


def new_context(request_id: str | None = None) -> ObservabilityContext:
    context = ObservabilityContext(request_id=request_id or str(uuid4()))
    _CONTEXT.set(context)
    return context


def get_context() -> ObservabilityContext:
    context = _CONTEXT.get()
    if context is None:
        context = new_context()
    return context


def set_context(**values: str | None) -> ObservabilityContext:
    context = get_context()
    for key, value in values.items():
        if hasattr(context, key) and value is not None:
            setattr(context, key, value)
    return context


def clear_context() -> None:
    _CONTEXT.set(None)  # type: ignore[arg-type]


def context_fields() -> dict[str, str]:
    context = get_context()
    return {
        key: value
        for key, value in {
            "request_id": context.request_id,
            "project_id": context.project_id,
            "revision_id": context.revision_id,
            "command_id": context.command_id,
            "generation_id": context.generation_id,
            "actor_id": context.actor_id,
        }.items()
        if value is not None
    }


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **context_fields(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if isinstance(getattr(record, "event_data", None), dict):
            payload["data"] = record.event_data
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(JsonLogFormatter())
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **data: Any) -> None:
    logger.log(level, event, extra={"event_data": data})
