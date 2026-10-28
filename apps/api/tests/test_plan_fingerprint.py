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


def test_command_type_and_schema_version_change_fingerprint() -> None:
    plan = CommandPlan("p", "project", "version", "rev", (PlanNode("a", "a"),))
    payloads = {"a": {"element_id": "e", "translation_m": {"x": 1.0, "y": 0.0, "z": 0.0}}}

    move_v1 = fingerprint_plan(
        plan, payloads, command_types={"a": "MoveBuilding"}, schema_versions={"a": 1}
    )
    move_v2 = fingerprint_plan(
        plan, payloads, command_types={"a": "MoveBuilding"}, schema_versions={"a": 2}
    )
    rotate_v1 = fingerprint_plan(
        plan, payloads, command_types={"a": "RotateBuilding"}, schema_versions={"a": 1}
    )

    assert move_v1 != move_v2
    assert move_v1 != rotate_v1
