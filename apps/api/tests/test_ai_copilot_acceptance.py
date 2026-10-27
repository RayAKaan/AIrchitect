import time

from app.domains.ai.approval import issue_approval_token
from app.domains.ai.copilot_acceptance import evaluate_copilot_acceptance
from app.domains.ai.copilot_plan import preview_proposal_plan
from app.domains.ai.proposals import AIProposal, ProposedCommand


def proposal() -> AIProposal:
    return AIProposal(
        proposal_id="proposal-1",
        project_id="project-1",
        version_id="version-1",
        base_revision_hash="revision-1",
        context_hash="context-1",
        intent="EDIT",
        summary="Update the program.",
        commands=(
            ProposedCommand(
                command_id="a",
                command_type="SetProgramArea",
                payload={"space_type": "courtyard", "area_m2": 120},
                reason="Set the requested area.",
            ),
        ),
        evidence_ids=("evidence-1",),
        confidence=0.9,
        provider="test",
        model="model",
        model_version="1",
    )


def test_acceptance_accepts_matching_token_and_revision() -> None:
    candidate = proposal()
    fingerprint = preview_proposal_plan(candidate).fingerprint
    assert fingerprint
    token = issue_approval_token(candidate, fingerprint, now=int(time.time()))

    result = evaluate_copilot_acceptance(
        candidate,
        approval_token=token,
        current_revision_hash="revision-1",
        allowed_evidence_ids={"evidence-1"},
    )

    assert result.accepted is True
    assert result.reasons == ()


def test_acceptance_rejects_stale_revision() -> None:
    candidate = proposal()
    fingerprint = preview_proposal_plan(candidate).fingerprint
    assert fingerprint
    token = issue_approval_token(candidate, fingerprint, now=int(time.time()))

    result = evaluate_copilot_acceptance(
        candidate,
        approval_token=token,
        current_revision_hash="revision-2",
        allowed_evidence_ids={"evidence-1"},
    )

    assert result.accepted is False
    assert "STALE_AI_PROPOSAL" in result.reasons


def test_acceptance_rejects_wrong_project_binding() -> None:
    candidate = proposal()
    fingerprint = preview_proposal_plan(candidate).fingerprint
    assert fingerprint
    token = issue_approval_token(candidate, fingerprint, now=int(time.time()))
    tampered = candidate.model_copy(update={"project_id": "project-2"})

    result = evaluate_copilot_acceptance(
        tampered,
        approval_token=token,
        current_revision_hash="revision-1",
        allowed_evidence_ids={"evidence-1"},
    )

    assert result.accepted is False
    assert "APPROVAL_TOKEN_SCOPE_MISMATCH" in result.reasons
