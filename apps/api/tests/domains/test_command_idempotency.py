import pytest
from app.domains.commands.idempotency import IdempotencyConflict, find_replay, record_command
from app.domains.commands.schemas import CommandEnvelope


def make(payload):
    return CommandEnvelope(
        command_id="same-command", type="MoveBuilding", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key="idem-12345678", payload=payload, reason="Move building",
    )


def test_same_command_is_replayed():
    state = {"history": []}
    command = make({"element_id": "b", "translation_m": {"x": 1}})
    record_command(state, command, {"status": "committed", "revision_hash": "r1"})
    assert find_replay(state, command)["result"]["revision_hash"] == "r1"


def test_reusing_command_id_with_new_payload_conflicts():
    state = {"history": []}
    record_command(state, make({"element_id": "b", "translation_m": {"x": 1}}), {"status": "committed"})
    with pytest.raises(IdempotencyConflict):
        find_replay(state, make({"element_id": "b", "translation_m": {"x": 2}}))
