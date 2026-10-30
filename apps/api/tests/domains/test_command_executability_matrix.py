from app.domains.commands.builtins import COMMANDS
from app.domains.commands.preview import preview_command
from app.domains.commands.schemas import CommandEnvelope
from app.domains.commands.geometry_adapter import supports_command
from app.domains.commands.semantic_adapter import supports_semantic_command


PAYLOADS = {
    "SetSiteBoundary": {"site_id": "site-1", "boundary": {}},
    "MoveBuilding": {"element_id": "building-1", "translation_m": {"x": 1, "y": 0, "z": 0}},
    "RotateBuilding": {"element_id": "building-1", "angle_deg": 90},
    "ChangeSetback": {"setback_m": 2},
    "AddLevel": {"building_id": "building-1", "elevation_m": 3},
    "ResizeSpace": {"element_id": "space-1", "area_m2": 40},
    "MoveSpace": {"element_id": "space-1", "translation_m": {"x": 1, "y": 0, "z": 0}},
    "SetProgramArea": {"space_type": "office", "area_m2": 40},
    "LockEntity": {"element_id": "space-1"},
    "Undo": {},
    "Redo": {},
}


def _command(command_type, payload):
    return CommandEnvelope(
        command_id=f"preview-{command_type}",
        type=command_type,
        schema_version=1,
        project_id="project-1",
        version_id="version-1",
        base_revision_hash="a" * 64,
        idempotency_key=f"preview-{command_type}-key",
        mode="preview",
        reason="Verify the command capability contract",
        payload=payload,
    )


def test_every_registered_command_has_an_explicit_valid_preview_contract():
    registered = {name for name, _ in COMMANDS}
    assert registered == set(PAYLOADS)
    for command_type, payload in PAYLOADS.items():
        preview = preview_command(_command(command_type, payload))
        assert preview.accepted, (command_type, preview.validation_errors)
        assert preview.executable is supports_command(command_type)
        if not preview.executable:
            assert preview.execution_blockers == [
                f"COMMAND_NOT_EXECUTABLE: {command_type} has no canonical mutation adapter"
            ]


def test_semantic_adapter_capabilities_remain_separate_from_geometry_commands():
    registered = {name for name, _ in COMMANDS}
    executable = {name for name in registered if supports_semantic_command(name)}
    assert executable == {"ResizeSpace", "LockEntity", "Undo", "Redo"}
    assert supports_command("MoveBuilding") is True
    assert supports_command("RotateBuilding") is False
