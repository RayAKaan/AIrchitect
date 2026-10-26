from app.domains.commands.plan import CommandPlan, PlanNode
from app.domains.commands.plan_execution import execute_plan
from app.domains.commands.schemas import CommandEnvelope


def command(
    command_id: str,
    *,
    project_id: str = "p",
    version_id: str = "v",
    revision: str = "r",
) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=command_id,
        type="ResizeSpace",
        schema_version=1,
        project_id=project_id,
        version_id=version_id,
        base_revision_hash=revision,
        idempotency_key=f"idempotent-{command_id}",
        mode="commit",
        reason="test",
        payload={"element_id": "e", "area_m2": 10.0},
    )


def test_plan_execution_accepts_matching_commands() -> None:
    commands = [command("a"), command("b")]
    plan = CommandPlan(
        "p1",
        "p",
        "v",
        "r",
        (PlanNode("a", "a"), PlanNode("b", "b", ("a",))),
    )
    model = {
        "project_id": "p",
        "project_version_id": "v",
        "designer_elements": [
            {
                "id": "e",
                "type": "Space",
                "element_type": "Space",
                "name": "e",
                "properties": {"area_m2": {"value": 5.0, "unit": "m2", "data_type": "number"}},
                "identity_key": "e",
                "designer_authored": True,
            }
        ],
        "semantic_model": {
            "elements": [
                {
                    "id": "e",
                    "type": "Space",
                    "element_type": "Space",
                    "identity_key": "e",
                    "area_m2": 5.0,
                }
            ],
            "spaces": [{"id": "e", "name": "e", "area_m2": 5.0}],
        },
        "spaces": [{"id": "e", "name": "e", "area_m2": 5.0}],
    }
    result = execute_plan(model, {}, plan, commands, "actor", "r")
    assert len(result.results) == 2


def test_plan_execution_rejects_mismatched_command_set() -> None:
    plan = CommandPlan("p1", "p", "v", "r", (PlanNode("a", "a"),))
    try:
        execute_plan({}, {}, plan, [command("b")], "actor", "r")
    except ValueError as exc:
        assert "command set" in str(exc)
    else:
        raise AssertionError("expected command-set rejection")


def test_plan_execution_rejects_mismatched_context() -> None:
    plan = CommandPlan("p1", "p", "v", "r", (PlanNode("a", "a"),))
    try:
        execute_plan({}, {}, plan, [command("a", project_id="other")], "actor", "r")
    except ValueError as exc:
        assert "context" in str(exc)
    else:
        raise AssertionError("expected context rejection")


def test_plan_execution_rejects_mismatched_revision() -> None:
    plan = CommandPlan("p1", "p", "v", "r", (PlanNode("a", "a"),))
    try:
        execute_plan({}, {}, plan, [command("a")], "actor", "stale")
    except ValueError as exc:
        assert "revision" in str(exc)
    else:
        raise AssertionError("expected revision rejection")
