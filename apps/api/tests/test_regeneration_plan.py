from app.domains.model.change_impact import ChangeImpact, ModelChange
from app.domains.model.regeneration_plan import build_regeneration_plan


def test_regeneration_plan_is_ordered_and_dependency_chained() -> None:
    impact = ChangeImpact(
        previous_hash="a" * 64,
        current_hash="b" * 64,
        changed_elements=(ModelChange("room", "updated"),),
        affected_elements=("room", "wall"),
        invalidated_artifacts=("regulatory", "cost", "geometry"),
    )
    plan = build_regeneration_plan(impact)
    assert [task.artifact_type for task in plan.tasks] == ["geometry", "cost", "regulatory"]
    assert plan.tasks[0].depends_on == ()
    assert plan.tasks[1].depends_on == (plan.tasks[0].task_id,)
    assert plan.tasks[2].depends_on == (plan.tasks[0].task_id, plan.tasks[1].task_id)
    assert all(task.source_revision_hash == "b" * 64 for task in plan.tasks)
