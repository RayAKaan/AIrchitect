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
