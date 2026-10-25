from app.domains.commands.plan import CommandPlan, PlanNode
from app.domains.commands.plan_dependency_graph import dependency_graph_for_plan


def test_plan_dependency_graph_preserves_dependency_direction() -> None:
    plan = CommandPlan(
        "plan",
        "project",
        "version",
        "revision",
        (
            PlanNode("building", "cmd-building"),
            PlanNode("analysis", "cmd-analysis", ("building",)),
            PlanNode("drawings", "cmd-drawings", ("analysis",)),
        ),
    )
    graph = dependency_graph_for_plan(plan)
    assert graph.topological_order() == ("building", "analysis", "drawings")
    assert graph.dependencies_of("drawings") == ("analysis",)
    assert graph.dependents_of("building") == ("analysis",)


def test_plan_dependency_graph_rejects_invalid_plan() -> None:
    plan = CommandPlan(
        "plan",
        "project",
        "version",
        "revision",
        (PlanNode("a", "cmd-a", ("missing",)),),
    )
    try:
        dependency_graph_for_plan(plan)
    except ValueError as exc:
        assert "unknown dependencies" in str(exc)
    else:
        raise AssertionError("expected invalid plan rejection")
