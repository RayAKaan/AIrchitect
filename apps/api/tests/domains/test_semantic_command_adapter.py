import pytest

from app.domains.commands.schemas import CommandEnvelope
from app.domains.commands.semantic_adapter import (
    semantic_edit_from_command,
    supports_semantic_command,
)


def make(command_type, payload):
    return CommandEnvelope(
        command_id="cmd-adapter-1", type=command_type, schema_version=1,
        project_id="p", version_id="v", base_revision_hash="hash",
        idempotency_key="adapter-12345678", payload=payload, reason="Update design intent",
    )


@pytest.mark.parametrize("command_type,payload", [
    ("MoveBuilding", {"element_id": "b", "translation_m": {"x": 1, "y": 0, "z": 0}}),
    ("RotateBuilding", {"element_id": "b", "angle_deg": 90}),
    ("MoveSpace", {"element_id": "s", "translation_m": {"x": 1, "y": 0, "z": 0}}),
])
def test_geometric_commands_are_not_claimed_by_semantic_property_adapter(command_type, payload):
    command = make(command_type, payload)
    assert supports_semantic_command(command_type) is False
    with pytest.raises(ValueError, match="not handled"):
        semantic_edit_from_command(command)


def test_resize_space_maps_to_area_property():
    command = make("ResizeSpace", {"element_id": "space-1", "area_m2": 42})
    assert supports_semantic_command("ResizeSpace") is True
    assert semantic_edit_from_command(command) == ("space-1", "area_m2", 42)


@pytest.mark.parametrize("command_type", ["LockEntity", "Undo", "Redo"])
def test_control_commands_are_owned_by_adapter(command_type):
    assert supports_semantic_command(command_type) is True


def test_unsupported_command_fails_closed():
    with pytest.raises(ValueError, match="not handled"):
        semantic_edit_from_command(make("SetSiteBoundary", {"site_id": "s", "boundary": {}}))
