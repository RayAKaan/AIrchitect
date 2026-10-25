from app.domains.commands.regeneration import build_regeneration_plan
from app.domains.commands.schemas import CommandEnvelope


def test_move_building_requires_downstream_recomputation():
    command = CommandEnvelope(
        command_id="regen-1", type="MoveBuilding", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key="regen-12345678", payload={"element_id": "b", "translation_m": {"x": 1}},
        reason="Move building",
    )
    plan = build_regeneration_plan(command)
    assert plan.requires_recomputation
    assert "parametric_geometry_intents" in plan.groups
