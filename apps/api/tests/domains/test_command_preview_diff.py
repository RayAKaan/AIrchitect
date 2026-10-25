from app.domains.commands.preview_diff import explain_command
from app.domains.commands.schemas import CommandEnvelope


def test_command_explanation_is_deterministic():
    command = CommandEnvelope(
        command_id="c", type="MoveBuilding", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key="idem-12345678", payload={"element_id": "b", "translation_m": {"x": 2, "y": 1}},
        reason="move",
    )
    assert explain_command(command)[0].after == {"x": 2.0, "y": 1.0, "z": 0.0}
