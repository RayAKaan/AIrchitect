from app.domains.commands.impact import impact_for
from app.domains.commands.schemas import CommandEnvelope


def test_change_setback_impacts_envelope_and_geometry():
    command = CommandEnvelope(
        command_id="impact-1", type="ChangeSetback", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key="impact-12345678", payload={"setback_m": 4}, reason="Adjust setback",
    )
    impact = impact_for(command)
    assert impact[:2] == ["planning_envelope", "design_alternatives"]
    assert "validation" in impact


def test_geometry_commands_invalidate_spatial_and_constraint_artifacts():
    command = CommandEnvelope(
        command_id="impact-space-1", type="MoveSpace", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key="impact-space-12345678",
        payload={"space_id": "space-1", "translation_m": {"x": 1, "y": 0, "z": 0}},
        reason="Move the space",
    )
    impact = impact_for(command)
    assert impact == [
        "spatial_layout",
        "spatial_topology",
        "architectural_elements",
        "architectural_constraints",
        "parametric_geometry_intents",
        "validation",
    ]
