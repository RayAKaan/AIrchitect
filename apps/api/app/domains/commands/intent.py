from __future__ import annotations

import re

from .schemas import CommandEnvelope


_PATTERNS = (
    (re.compile(r"\bmove building\b", re.I), "MoveBuilding"),
    (re.compile(r"\brotate building\b", re.I), "RotateBuilding"),
    (re.compile(r"\bresize space\b", re.I), "ResizeSpace"),
    (re.compile(r"\bundo\b", re.I), "Undo"),
)


def propose_command(text: str, *, project_id: str, version_id: str, base_revision_hash: str, command_id: str, idempotency_key: str) -> CommandEnvelope | None:
    """Map only unambiguous phrases to a typed command; never silently invent values."""
    normalized = text.strip()
    for pattern, command_type in _PATTERNS:
        if pattern.search(normalized):
            return CommandEnvelope(
                command_id=command_id,
                type=command_type,
                schema_version=1,
                project_id=project_id,
                version_id=version_id,
                base_revision_hash=base_revision_hash,
                idempotency_key=idempotency_key,
                payload={},
                mode="preview",
                reason=normalized[:500],
            )
    return None
