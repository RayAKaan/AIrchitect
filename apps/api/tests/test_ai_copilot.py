import pytest

from app.db.models import DecisionRecord
from app.domains.ai.copilot_commit import replay_result
from app.domains.ai.proposals import AIProposalDraft, ProposedCommand


def test_copilot_draft_is_bounded_and_confirmation_defaults_true() -> None:
    draft = AIProposalDraft(
        intent="DESIGN",
        summary="Generate two concept alternatives.",
        commands=(
            ProposedCommand(
                command_id="concept-1",
                command_type="GenerateDesignAlternative",
                payload={"strategy": "courtyard"},
                reason="Explore the requested courtyard organization.",
            ),
        ),
        evidence_ids=("evidence-1",),
        confidence=0.88,
    )

    assert draft.requires_confirmation is True
    assert draft.commands[0].command_type == "GenerateDesignAlternative"


def test_copilot_replay_decodes_immutable_execution_result() -> None:
    record = DecisionRecord(
        outputs_json={"revision_hash": "revision-2", "results": [{"command_id": "a", "status": "applied"}]},
    )

    results, revision_hash = replay_result(record)

    assert revision_hash == "revision-2"
    assert results == ({"command_id": "a", "status": "applied"},)


def test_copilot_replay_fails_closed_on_corrupt_audit_record() -> None:
    record = DecisionRecord(outputs_json={"results": []})

    with pytest.raises(ValueError, match="COPILOT_AUDIT_CORRUPT"):
        replay_result(record)
