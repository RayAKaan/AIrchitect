import pytest

from app.domains.lifecycle.pipeline_planner import plan_pipeline


def test_pipeline_plan_is_stable() -> None:
    plan = plan_pipeline(
        {"geometry", "quantities", "cost"},
        {"quantities": {"geometry"}, "cost": {"quantities"}},
    )
    assert plan.stages == ("geometry", "quantities", "cost")


def test_pipeline_plan_rejects_cycles() -> None:
    with pytest.raises(ValueError, match="cycle"):
        plan_pipeline({"a", "b"}, {"a": {"b"}, "b": {"a"}})


def test_pipeline_plan_rejects_unknown_dependencies() -> None:
    with pytest.raises(ValueError, match="unknown"):
        plan_pipeline({"geometry"}, {"geometry": {"missing"}})
