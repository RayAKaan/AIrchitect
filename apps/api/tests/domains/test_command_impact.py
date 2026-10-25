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
