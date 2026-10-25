from app.domains.commands.plan import CommandPlan, PlanNode
from app.domains.commands.plan_contract import contract_for


def test_valid_plan_is_executable() -> None:
    plan = CommandPlan("p", "project", "version", "rev", (PlanNode("a", "a"),))
    result = contract_for(plan)
    assert result.executable is True
    assert result.reason is None


def test_invalid_plan_is_not_executable() -> None:
    plan = CommandPlan("p", "project", "version", "rev", (PlanNode("a", "a", ("missing",)),))
    result = contract_for(plan)
    assert result.executable is False
    assert result.reason
