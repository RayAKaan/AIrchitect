from app.domains.commands.regeneration import RegenerationPlan
from app.domains.commands.regeneration_engine import execution_steps


def test_regeneration_steps_are_topologically_stable():
    plan = RegenerationPlan("c", "h", ("analysis", "semantic_model", "parametric_geometry_intents", "analysis"), True)
    steps = execution_steps(plan)
    assert [step.group for step in steps] == ["semantic_model", "parametric_geometry_intents", "analysis"]


def test_unknown_regeneration_group_fails_closed():
    plan = RegenerationPlan("c", "h", ("mystery",), True)
    try:
        execution_steps(plan)
    except ValueError as exc:
        assert "mystery" in str(exc)
    else:
        raise AssertionError("expected unknown regeneration group to fail")
