from app.domains.commands.executor import execute_semantic_command
from app.domains.commands.schemas import CommandEnvelope


def test_executor_requires_commit_mode():
    command = CommandEnvelope(
        command_id="exec-1", type="MoveBuilding", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key="exec-12345678", payload={"element_id": "b", "translation_m": {"x": 1}},
        reason="Move building", mode="preview",
    )
    try:
        execute_semantic_command({"elements": []}, {"history": []}, command, "u", "r")
    except ValueError as exc:
        assert "commit mode" in str(exc)
    else:
        raise AssertionError("preview command was executed")
