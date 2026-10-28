from app.domains.commands.preview import preview_command
from app.domains.commands.schemas import CommandEnvelope


def test_preview_never_reports_canonical_mutation():
    command = CommandEnvelope(
        command_id="cmd-preview-1",
        type="ChangeSetback",
        schema_version=1,
        project_id="project-1",
        version_id="version-1",
        base_revision_hash="sha256:base",
        idempotency_key="preview-12345678",
        payload={"setback_m": 5},
        mode="preview",
        reason="Test planning change",
    )
    result = preview_command(command)
    assert result.accepted
    assert result.executable is False
    assert "COMMAND_NOT_EXECUTABLE" in result.execution_blockers[0]
    assert result.canonical_mutation is False
