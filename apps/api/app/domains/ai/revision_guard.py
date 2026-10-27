from __future__ import annotations

from dataclasses import dataclass

from .proposals import AIProposal


@dataclass(frozen=True)
class RevisionValidation:
    current: bool
    error: str | None = None


def validate_proposal_revision(proposal: AIProposal, current_revision_hash: str) -> RevisionValidation:
    """Reject proposals computed against a superseded canonical revision."""

    if not current_revision_hash.strip():
        return RevisionValidation(False, "CURRENT_REVISION_MISSING")
    if proposal.base_revision_hash != current_revision_hash:
        return RevisionValidation(False, "STALE_AI_PROPOSAL")
    return RevisionValidation(True)
