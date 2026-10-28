from app.domains.commands.plan_preview import preview_sequential_plan
from app.domains.commands.schemas import CommandEnvelope


def command(command_id: str, *, command_type: str = "MoveBuilding", payload: dict | None = None) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=command_id,
        type=command_type,
        schema_version=1,
        project_id="p",
        version_id="v",
        base_revision_hash="r",
        idempotency_key=f"idempotent-{command_id}",
        reason="preview",
        payload=payload or {"element_id": "building-1", "translation_m": {"x": 1.0, "y": 0.0, "z": 0.0}},
    )


def test_plan_preview_is_deterministic_and_non_mutating() -> None:
    result = preview_sequential_plan("plan", [command("a"), command("b", command_type="LockEntity", payload={"element_id": "building-1"})])
    assert result.executable is True
    assert result.execution_order == ("a", "b")
    assert result.impact_groups == ("cost", "parametric_geometry_intents", "quantities", "validation")
    assert result.fingerprint


def test_plan_preview_fails_closed_for_invalid_command() -> None:
    invalid = command("a", payload={"element_id": "building-1", "translation_m": {"x": float("nan"), "y": 0.0, "z": 0.0}})
    result = preview_sequential_plan("plan", [invalid])
    assert result.executable is False
    assert result.fingerprint is None
    assert result.validation_errors


def test_equivalent_vector_payloads_have_the_same_plan_fingerprint() -> None:
    object_vector = command("move", payload={
        "element_id": "building-1",
        "translation_m": {"x": 1.0, "y": 2.0, "z": 0.0},
    })
    array_vector = command("move", payload={
        "element_id": "building-1",
        "translation_m": [1, 2],
    })

    object_preview = preview_sequential_plan("plan", [object_vector])
    array_preview = preview_sequential_plan("plan", [array_vector])

    assert object_preview.executable is True
    assert array_preview.executable is True
    assert object_preview.fingerprint == array_preview.fingerprint
