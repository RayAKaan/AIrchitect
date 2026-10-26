from app.domains.commands.batch_contract import validate_command_batch
from app.domains.commands.schemas import CommandEnvelope


def command(command_id: str) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=command_id,
        type="MoveBuilding",
        schema_version=1,
        project_id="p",
        version_id="v",
        base_revision_hash="r",
        idempotency_key=f"idempotent-{command_id}",
        reason="test",
    )


def test_batch_accepts_consistent_commands() -> None:
    validate_command_batch([command("a"), command("b")])


def test_batch_rejects_duplicate_ids() -> None:
    try:
        validate_command_batch([command("a"), command("a")])
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("expected duplicate-id rejection")
