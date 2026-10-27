from __future__ import annotations

from dataclasses import dataclass

from app.domains.ai.approval import verify_approval_token
from app.domains.ai.copilot_plan import preview_proposal_plan
from app.domains.ai.proposals import AIProposal, validate_ai_proposal, validate_proposal_evidence
from app.domains.ai.revision_guard import validate_proposal_revision
from app.domains.lifecycle.service import canonical_hash


@dataclass(frozen=True)
class CopilotAcceptance:
    accepted: bool
    reasons: tuple[str, ...] = ()


def evaluate_copilot_acceptance(
    proposal: AIProposal,
    *,
    approval_token: str,
    current_revision_hash: str,
    allowed_evidence_ids: set[str],
) -> CopilotAcceptance:
    """Evaluate every pre-commit Copilot invariant without mutating state."""

    reasons: list[str] = []

    proposal_validation = validate_ai_proposal(proposal)
    reasons.extend(proposal_validation.errors)

    evidence_validation = validate_proposal_evidence(proposal, allowed_evidence_ids)
    reasons.extend(evidence_validation.errors)

    revision = validate_proposal_revision(proposal, current_revision_hash)
    if not revision.current and revision.error:
        reasons.append(revision.error)

    try:
        claims = verify_approval_token(approval_token)
    except ValueError as exc:
        reasons.append(str(exc))
        claims = None

    preview = None
    if not reasons:
        try:
            preview = preview_proposal_plan(proposal)
        except ValueError as exc:
            reasons.append(str(exc))

    if claims is not None:
        if claims.proposal_id != proposal.proposal_id:
            reasons.append("APPROVAL_TOKEN_PROPOSAL_MISMATCH")
        if claims.project_id != proposal.project_id or claims.version_id != proposal.version_id:
            reasons.append("APPROVAL_TOKEN_SCOPE_MISMATCH")
        if claims.proposal_hash != canonical_hash(proposal.model_dump(mode="json")):
            reasons.append("APPROVAL_TOKEN_PROPOSAL_MISMATCH")
        if claims.base_revision_hash != current_revision_hash:
            reasons.append("APPROVAL_TOKEN_REVISION_MISMATCH")
        if preview is not None and claims.plan_fingerprint != preview.fingerprint:
            reasons.append("APPROVAL_TOKEN_PLAN_MISMATCH")

    if preview is not None and not preview.executable:
        reasons.extend(preview.validation_errors)

    return CopilotAcceptance(accepted=not reasons, reasons=tuple(dict.fromkeys(reasons)))
