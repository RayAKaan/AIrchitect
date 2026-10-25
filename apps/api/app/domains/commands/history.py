from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CommandHistoryEntry:
    command_id: str
    command_type: str
    actor_id: str
    project_id: str
    version_id: str
    base_revision_hash: str
    resulting_revision_hash: str
    reason: str
    created_at: datetime
    status: str


def history_summary(entries: list[CommandHistoryEntry]) -> dict[str, object]:
    """Produce a stable, newest-first history projection without mutating entries."""
    ordered = sorted(entries, key=lambda item: item.created_at, reverse=True)
    return {
        "count": len(ordered),
        "entries": [
            {
                "command_id": item.command_id,
                "command_type": item.command_type,
                "actor_id": item.actor_id,
                "project_id": item.project_id,
                "version_id": item.version_id,
                "base_revision_hash": item.base_revision_hash,
                "resulting_revision_hash": item.resulting_revision_hash,
                "reason": item.reason,
                "created_at": item.created_at.isoformat(),
                "status": item.status,
            }
            for item in ordered
        ],
    }
