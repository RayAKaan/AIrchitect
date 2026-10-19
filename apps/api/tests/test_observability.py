from __future__ import annotations

import json
import logging

from app.core.observability import JsonLogFormatter, clear_context, context_fields, new_context, set_context


def test_observability_context_tracks_request_and_domain_identifiers() -> None:
    clear_context()
    new_context("request-123")
    set_context(project_id="project-1", revision_id="revision-2", command_id="command-3", generation_id="generation-4", actor_id="user-5")

    assert context_fields() == {
        "request_id": "request-123",
        "project_id": "project-1",
        "revision_id": "revision-2",
        "command_id": "command-3",
        "generation_id": "generation-4",
        "actor_id": "user-5",
    }
    clear_context()


def test_json_log_formatter_emits_context_and_event_data() -> None:
    clear_context()
    new_context("request-123")
    set_context(project_id="project-1")
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "completed", (), None)
    record.event_data = {"status_code": 200, "duration_ms": 12.5}  # type: ignore[attr-defined]

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["message"] == "completed"
    assert payload["request_id"] == "request-123"
    assert payload["project_id"] == "project-1"
    assert payload["data"] == {"status_code": 200, "duration_ms": 12.5}
    clear_context()
