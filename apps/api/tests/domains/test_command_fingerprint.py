from app.domains.commands.fingerprint import command_fingerprint, payload_hash
from app.domains.commands.schemas import CommandEnvelope


def make(payload):
    return CommandEnvelope(
        command_id="fingerprint-1", type="MoveBuilding", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key="fingerprint-12345678", payload=payload, reason="Move building",
    )


def test_payload_hash_is_order_independent():
    assert payload_hash(make({"b": 2, "a": 1})) == payload_hash(make({"a": 1, "b": 2}))


def test_fingerprint_changes_when_payload_changes():
    assert command_fingerprint(make({"a": 1})) != command_fingerprint(make({"a": 2}))
