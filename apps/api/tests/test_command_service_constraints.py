from __future__ import annotations

from app.domains.commands.schemas import CommandEnvelope
from app.domains.commands.service import validate_command


def make(command_type: str, payload: dict[str, object]) -> CommandEnvelope:
    return CommandEnvelope(command_id="c", type=command_type, schema_version=1, project_id="p", version_id="v", base_revision_hash="h", idempotency_key="abcdefgh", payload=payload, reason="test")


def test_service_rejects_invalid_architectural_values() -> None:
    result = validate_command(make("ChangeSetback", {"setback_m": -0.1}))
    assert result.valid is False
    assert result.errors == ["setback_m must be >= 0"]


def test_service_preserves_valid_command_path() -> None:
    result = validate_command(make("MoveBuilding", {"element_id": "b1", "translation_m": {"x": 1, "y": 2, "z": 0}}))
    assert result.valid is True
