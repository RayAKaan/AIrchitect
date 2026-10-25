from app.domains.commands.intent import propose_command


def test_ambiguous_text_returns_no_command():
    assert propose_command("make it better", project_id="p", version_id="v", base_revision_hash="h", command_id="i", idempotency_key="intent-12345678") is None


def test_explicit_intent_produces_preview_candidate():
    proposal = propose_command("Move building toward the road", project_id="p", version_id="v", base_revision_hash="h", command_id="i", idempotency_key="intent-12345678")
    assert proposal is not None
    assert proposal.type == "MoveBuilding"
    assert proposal.mode == "preview"
