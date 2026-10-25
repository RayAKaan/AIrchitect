from __future__ import annotations

from typing import Any

from .fingerprint import command_fingerprint
from .schemas import CommandEnvelope


class IdempotencyConflict(ValueError):
    pass


def find_replay(state: dict[str, Any], command: CommandEnvelope) -> dict[str, Any] | None:
    fingerprint = command_fingerprint(command)
    for event in reversed(state.get("history", [])):
        if event.get("command_id") != command.command_id:
            continue
        if event.get("fingerprint") != fingerprint:
            raise IdempotencyConflict("command_id was already used with a different payload")
        return event
    return None


def record_command(state: dict[str, Any], command: CommandEnvelope, result: dict[str, Any]) -> None:
    state.setdefault("history", []).append({
        "command_id": command.command_id,
        "fingerprint": command_fingerprint(command),
        "command_type": command.type,
        "status": result.get("status", "committed"),
        "result": result,
    })
