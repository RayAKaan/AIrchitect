import pytest

from app.domains.commands.schemas import CommandEnvelope
from app.domains.commands.semantic_adapter import semantic_edit_from_command


def make(command_type, payload):
    return CommandEnvelope(
        command_id="cmd-adapter-1", type=command_type, schema_version=1,
        project_id="p", version_id="v", base_revision_hash="hash",
        idempotency_key="adapter-12345678", payload=payload, reason="Update design intent",
    )


def test_move_building_maps_to_translation():
    assert semantic_edit_from_command(make("MoveBuilding", {"element_id": "b", "translation_m": {"x": 1}})) == ("b", "translation_m", {"x": 1})


def test_unsupported_command_fails_closed():
    with pytest.raises(ValueError, match="not handled"):
        semantic_edit_from_command(make("SetSiteBoundary", {"site_id": "s", "boundary": {}}))
