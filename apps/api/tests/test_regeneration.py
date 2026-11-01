from app.domains.commands.plan import CommandPlan, PlanNode
from app.domains.commands.regeneration import build_regeneration_batch_plan, build_regeneration_plan
from app.domains.commands.schemas import CommandEnvelope


def command(command_id: str, command_type: str = "MoveBuilding", revision: str = "r") -> CommandEnvelope:
    payload = {"element_id": "building-1", "translation_m": {"x": 1.0, "y": 0.0}}
    if command_type == "LockEntity":
        payload = {"element_id": "building-1"}
    return CommandEnvelope(
        command_id=command_id,
        type=command_type,
        schema_version=1,
        project_id="p",
        version_id="v",
        base_revision_hash=revision,
        idempotency_key=f"idempotent-{command_id}",
        reason="regeneration",
        payload=payload,
    )


def test_single_command_regeneration_projection_remains_compatible() -> None:
    result = build_regeneration_plan(command("a"))
    assert result.command_id == "a"
    assert result.requires_recomputation is True


def test_batch_regeneration_follows_dependency_order_and_aggregates_impact() -> None:
    commands = [command("building"), command("lock", "LockEntity")]
    plan = CommandPlan(
        "plan",
        "p",
        "v",
        "r",
        (PlanNode("building", "building"), PlanNode("lock", "lock", ("building",))),
    )
    result = build_regeneration_batch_plan(plan, commands)
    assert result.command_order == ("building", "lock")
    assert result.invalidated_groups == ("cost", "design_alternatives", "parametric_geometry_intents", "quantities", "validation")
    assert result.requires_recomputation is True


def test_batch_regeneration_rejects_wrong_revision() -> None:
    plan = CommandPlan("plan", "p", "v", "r", (PlanNode("a", "a"),))
    try:
        build_regeneration_batch_plan(plan, [command("a", revision="stale")])
    except ValueError as exc:
        assert "revision" in str(exc)
    else:
        raise AssertionError("expected revision rejection")
