import pytest

from app.domains.commands.batch import execute_command_batch
from app.domains.commands.schemas import CommandEnvelope


def _command(command_id: str, element_id: str = "b") -> CommandEnvelope:
    return CommandEnvelope(
        command_id=command_id, type="MoveBuilding", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key=f"idem-{command_id}-1234", payload={"element_id": element_id, "translation_m": {"x": 1, "y": 0}},
        mode="commit", reason="batch move",
    )


def test_batch_does_not_partially_mutate_on_failure():
    model = {"semantic_model": {"elements": [{"id": "b", "type": "Building"}]}}
    state = {"locks": {}, "history": []}
    with pytest.raises(ValueError):
        execute_command_batch(model, state, [_command("a"), _command("b", "missing")], "u", "h")
    assert model == {"semantic_model": {"elements": [{"id": "b", "type": "Building"}]}}
    assert state == {"locks": {}, "history": []}
