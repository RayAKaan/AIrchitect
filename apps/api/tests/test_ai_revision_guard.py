from app.domains.ai.proposals import AIProposal
from app.domains.ai.revision_guard import validate_proposal_revision


def proposal() -> AIProposal:
    return AIProposal(
        proposal_id="p",
        project_id="project",
        version_id="version",
        base_revision_hash="revision-a",
        context_hash="context",
        intent="EDIT",
        summary="Change the courtyard.",
        confidence=0.9,
        provider="test",
        model="model",
        model_version="1",
    )


def test_current_revision_is_accepted() -> None:
    result = validate_proposal_revision(proposal(), "revision-a")
    assert result.current is True
    assert result.error is None


def test_stale_revision_is_rejected() -> None:
    result = validate_proposal_revision(proposal(), "revision-b")
    assert result.current is False
    assert result.error == "STALE_AI_PROPOSAL"


def test_missing_current_revision_fails_closed() -> None:
    result = validate_proposal_revision(proposal(), "   ")
    assert result.current is False
    assert result.error == "CURRENT_REVISION_MISSING"
