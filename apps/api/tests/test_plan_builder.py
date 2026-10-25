from app.domains.commands.plan_builder import build_sequential_plan
from app.domains.commands.schemas import CommandEnvelope


def command(command_id: str) -> CommandEnvelope:
    return CommandEnvelope(command_id=command_id, type="MoveBuilding", schema_version=1, project_id="p", version_id="v", base_revision_hash="r", idempotency_key=f"idem-{command_id}", reason="test")


def test_builder_links_commands_in_order() -> None:
    plan = build_sequential_plan("plan", [command("a"), command("b"), command("c")])
    assert plan.execution_order() == ("a", "b", "c")


def test_builder_rejects_mixed_versions() -> None:
    first = command("a")
    second = command("b").model_copy(update={"version_id": "other"})
    try:
        build_sequential_plan("plan", [first, second])
    except ValueError as exc:
        assert "same project and version" in str(exc)
    else:
        raise AssertionError("expected mixed-version rejection")
