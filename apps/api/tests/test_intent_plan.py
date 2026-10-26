from app.domains.commands.intent_plan import build_intent_plan
from app.domains.commands.schemas import CommandEnvelope


def command(command_id: str) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=command_id,
        type="MoveBuilding",
        schema_version=1,
        project_id="p",
        version_id="v",
        base_revision_hash="r",
        idempotency_key=f"idempotent-{command_id}",
        reason="intent",
    )


def test_intent_plan_preserves_command_order_without_inference() -> None:
    plan = build_intent_plan("plan", [command("a"), command("b")])
    assert plan.execution_order() == ("a", "b")
