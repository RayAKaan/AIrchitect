from app.domains.commands.schemas import CommandEnvelope
from app.domains.commands.service import validate_command


def command(**overrides):
    data = {
        "command_id": "cmd-123",
        "type": "MoveBuilding",
        "schema_version": 1,
        "project_id": "project-1",
        "version_id": "version-1",
        "base_revision_hash": "sha256:base",
        "idempotency_key": "idem-12345678",
        "payload": {"element_id": "building-1", "translation_m": {"x": 1, "y": 0, "z": 0}},
        "reason": "Move the building for frontage alignment",
    }
    data.update(overrides)
    return CommandEnvelope.model_validate(data)


def test_known_command_validates():
    result = validate_command(command())
    assert result.valid
    assert result.errors == []


def test_unknown_command_fails_closed():
    result = validate_command(command(type="InventedCommand"))
    assert not result.valid
    assert "unsupported command" in result.errors[0]


def test_missing_payload_is_rejected():
    result = validate_command(command(payload={"element_id": "building-1"}))
    assert not result.valid
    assert "translation_m" in result.errors[0]
