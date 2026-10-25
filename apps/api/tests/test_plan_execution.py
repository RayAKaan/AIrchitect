from app.domains.commands.plan import CommandPlan, PlanNode
from app.domains.commands.plan_execution import execute_plan
from app.domains.commands.schemas import CommandEnvelope


def command(command_id: str) -> CommandEnvelope:
    return CommandEnvelope(command_id=command_id, type="LockEntity", schema_version=1, project_id="p", version_id="v", base_revision_hash="r", idempotency_key=f"idem-{command_id}", reason="test", payload={"element_id": "e"})


def test_plan_execution_accepts_matching_commands() -> None:
    commands = [command("a"), command("b")]
    plan = CommandPlan("p1", "p", "v", "r", (PlanNode("a", "a"), PlanNode("b", "b", ("a",))))
    result = execute_plan({}, {}, plan, commands, "actor", "r")
    assert len(result.results) == 2


def test_plan_execution_rejects_mismatched_command_set() -> None:
    plan = CommandPlan("p1", "p", "v", "r", (PlanNode("a", "a"),))
    try:
        execute_plan({}, {}, plan, [command("b")], "actor", "r")
    except ValueError as exc:
        assert "command set" in str(exc)
    else:
        raise AssertionError("expected command-set rejection")
