from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


RegenerationStatus = Literal["CURRENT", "INVALIDATED", "STALE", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]

_ALLOWED_TRANSITIONS: dict[RegenerationStatus, frozenset[RegenerationStatus]] = {
    "CURRENT": frozenset({"INVALIDATED"}),
    "INVALIDATED": frozenset({"STALE"}),
    "STALE": frozenset({"QUEUED"}),
    "QUEUED": frozenset({"RUNNING"}),
    "RUNNING": frozenset({"SUCCEEDED", "FAILED"}),
    "SUCCEEDED": frozenset({"CURRENT", "INVALIDATED"}),
    "FAILED": frozenset({"QUEUED", "INVALIDATED"}),
}


@dataclass(frozen=True)
class RegenerationState:
    artifact_id: str
    source_revision_hash: str
    status: RegenerationStatus
    output_revision_hash: str | None = None

    def transition(self, status: RegenerationStatus, *, output_revision_hash: str | None = None) -> "RegenerationState":
        if status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"invalid regeneration transition: {self.status} -> {status}")
        if status == "CURRENT" and output_revision_hash != self.source_revision_hash:
            raise ValueError("current regeneration output must match its source revision")
        if status != "CURRENT" and output_revision_hash is not None:
            raise ValueError("output revision is only set when regeneration becomes current")
        return replace(self, status=status, output_revision_hash=output_revision_hash)


def invalidate(state: RegenerationState, source_revision_hash: str) -> RegenerationState:
    if source_revision_hash == state.source_revision_hash and state.status == "CURRENT":
        return state
    invalidated = replace(state, source_revision_hash=source_revision_hash, output_revision_hash=None)
    if state.status == "CURRENT":
        invalidated = invalidated.transition("INVALIDATED")
    elif state.status not in {"INVALIDATED", "STALE", "QUEUED", "RUNNING"}:
        invalidated = invalidated.transition("INVALIDATED")
    return invalidated
