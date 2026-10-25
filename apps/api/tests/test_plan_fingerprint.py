from app.domains.commands.plan import CommandPlan, PlanNode
from app.domains.commands.plan_fingerprint import fingerprint_plan


def test_fingerprint_is_stable() -> None:
    plan = CommandPlan("p", "project", "version", "rev", (PlanNode("a", "a"),))
    first = fingerprint_plan(plan, {"a": {"x": 1, "y": 2}})
    second = fingerprint_plan(plan, {"a": {"y": 2, "x": 1}})
    assert first == second


def test_payload_change_changes_fingerprint() -> None:
    plan = CommandPlan("p", "project", "version", "rev", (PlanNode("a", "a"),))
    assert fingerprint_plan(plan, {"a": {"x": 1}}) != fingerprint_plan(plan, {"a": {"x": 2}})
