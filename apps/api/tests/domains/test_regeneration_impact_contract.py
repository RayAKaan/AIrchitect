from app.domains.commands.artifact_invalidation import GROUP_TO_ARTIFACT_TYPE
from app.domains.commands.impact import IMPACT_GROUPS
from app.domains.commands.regeneration import RegenerationPlan
from app.domains.commands.regeneration_engine import execution_steps


def test_every_command_impact_group_has_a_mapping_and_execution_order():
    declared_groups = {
        group
        for groups in IMPACT_GROUPS.values()
        for group in groups
    }
    assert declared_groups <= set(GROUP_TO_ARTIFACT_TYPE)

    plan = RegenerationPlan(
        command_id="impact-contract",
        source_revision_hash="a" * 64,
        groups=tuple(sorted(declared_groups)),
        requires_recomputation=True,
    )
    steps = execution_steps(plan)

    assert {step.group for step in steps} == declared_groups
    assert [step.ordinal for step in steps] == sorted(step.ordinal for step in steps)


def test_regeneration_order_places_geometry_before_quantities_and_validation_last():
    plan = RegenerationPlan(
        command_id="dependency-order",
        source_revision_hash="b" * 64,
        groups=(
            "validation",
            "quantities",
            "parametric_geometry_intents",
            "design_alternatives",
            "planning_envelope",
        ),
        requires_recomputation=True,
    )
    ordered = [step.group for step in execution_steps(plan)]

    assert ordered.index("planning_envelope") < ordered.index("design_alternatives")
    assert ordered.index("design_alternatives") < ordered.index("parametric_geometry_intents")
    assert ordered.index("parametric_geometry_intents") < ordered.index("quantities")
    assert ordered[-1] == "validation"
