from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HistoryEntry:
    sequence: int
    command_id: str
    command_type: str
    fingerprint: str
    status: str


def project_history(state: dict[str, Any], *, limit: int = 100, after: int = 0) -> tuple[HistoryEntry, ...]:
    """Project immutable command history without exposing mutable event payloads."""
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")
    events = state.get("history", [])
    projected: list[HistoryEntry] = []
    for index, event in enumerate(events, start=1):
        if index <= after:
            continue
        projected.append(HistoryEntry(
            sequence=index,
            command_id=str(event.get("command_id", "")),
            command_type=str(event.get("command_type", "")),
            fingerprint=str(event.get("fingerprint", "")),
            status=str(event.get("status", "")),
        ))
        if len(projected) >= limit:
            break
    return tuple(projected)
