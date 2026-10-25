from app.domains.commands.plan import CommandPlan, PlanNode


def test_plan_orders_dependencies_deterministically() -> None:
    plan = CommandPlan("p", "project", "version", "rev", (
        PlanNode("b", "cmd-b", ("a",)),
        PlanNode("a", "cmd-a"),
        PlanNode("c", "cmd-c", ("a",)),
    ))
    assert plan.execution_order() == ("a", "b", "c")


def test_plan_rejects_cycles() -> None:
    plan = CommandPlan("p", "project", "version", "rev", (
        PlanNode("a", "cmd-a", ("b",)),
        PlanNode("b", "cmd-b", ("a",)),
    ))
    try:
        plan.validate()
    except ValueError as exc:
        assert "cycle" in str(exc)
    else:
        raise AssertionError("expected cycle rejection")


def test_plan_rejects_duplicate_command_ids() -> None:
    plan = CommandPlan("p", "project", "version", "rev", (
        PlanNode("a", "cmd"),
        PlanNode("b", "cmd"),
    ))
    try:
        plan.validate()
    except ValueError as exc:
        assert "command ids" in str(exc)
    else:
        raise AssertionError("expected duplicate command-id rejection")
