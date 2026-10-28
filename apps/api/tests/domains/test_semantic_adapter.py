from __future__ import annotations

from app.domains.commands.executor import execute_semantic_command
from app.domains.commands.schemas import CommandEnvelope


def test_lock_entity_updates_canonical_designer_state() -> None:
    model = {
        "semantic_model": {
            "elements": [
                {"id": "space-1", "element_type": "Space", "type": "Space", "name": "Office"},
            ],
        },
    }
    state = {"locks": {}, "history": [], "undo_stack": [], "redo_stack": []}
    command = CommandEnvelope(
        command_id="lock-space-1",
        type="LockEntity",
        schema_version=1,
        project_id="project-1",
        version_id="version-1",
        base_revision_hash="revision-hash",
        idempotency_key="lock-space-idempotency-1",
        mode="commit",
        reason="protect reviewed space",
        payload={"element_id": "space-1"},
    )

    result = execute_semantic_command(model, state, command, "actor-1", "revision-hash")

    assert result.status == "committed"
    assert result.canonical_mutation is True
    assert state["locks"]["space-1"]["locked"] is True
    assert state["locks"]["space-1"]["reason"] == "protect reviewed space"
    assert model["designer_state"] is state

