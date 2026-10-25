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
