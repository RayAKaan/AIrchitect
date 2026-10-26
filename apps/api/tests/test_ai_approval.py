import time

from app.domains.ai.approval import issue_approval_token, verify_approval_token
from app.domains.ai.proposals import AIProposal


def proposal() -> AIProposal:
    return AIProposal(
        proposal_id="proposal-1",
        project_id="project-1",
        version_id="version-1",
        base_revision_hash="revision-1",
        context_hash="context-1",
        intent="EDIT",
        summary="Update the program.",
        confidence=0.9,
        provider="test",
        model="model",
        model_version="1",
    )


def test_approval_token_round_trips() -> None:
    token = issue_approval_token(proposal(), "fingerprint-1", ttl_seconds=60, now=100)
    claims = verify_approval_token(token, now=120)

    assert claims.proposal_id == "proposal-1"
    assert claims.plan_fingerprint == "fingerprint-1"
    assert claims.proposal_hash
    assert claims.expires_at == 160


def test_approval_token_rejects_tampering() -> None:
    token = issue_approval_token(proposal(), "fingerprint-1", now=int(time.time()))
    encoded = token.rsplit(".", 1)[0]
    tampered = f"{encoded}x.invalid"

    try:
        verify_approval_token(tampered)
    except ValueError as exc:
        assert str(exc) == "INVALID_APPROVAL_TOKEN"
    else:
        raise AssertionError("expected token rejection")


def test_approval_token_expires() -> None:
    token = issue_approval_token(proposal(), "fingerprint-1", ttl_seconds=10, now=100)

    try:
        verify_approval_token(token, now=110)
    except ValueError as exc:
        assert str(exc) == "APPROVAL_TOKEN_EXPIRED"
    else:
        raise AssertionError("expected expiry rejection")
