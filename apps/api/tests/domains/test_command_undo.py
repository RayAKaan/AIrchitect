from app.domains.commands.schemas import CommandEnvelope
from app.domains.commands.impact import impact_for
from app.domains.commands.semantic_adapter import apply_semantic_command


def test_undo_is_registered_and_has_no_precomputed_dependency_impact():
    command = CommandEnvelope(
        command_id="undo-1", type="Undo", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key="undo-12345678", payload={}, reason="Undo last change",
    )
    assert impact_for(command) == []
