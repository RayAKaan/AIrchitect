from app.domains.commands.plan_preview import preview_sequential_plan
from app.domains.commands.schemas import CommandEnvelope


def command(command_id: str, *, command_type: str = "ResizeSpace", payload: dict | None = None, schema_version: int = 1) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=command_id,
        type=command_type,
        schema_version=schema_version,
        project_id="p",
        version_id="v",
        base_revision_hash="r",
        idempotency_key=f"idempotent-{command_id}",
        reason="preview",
        payload=payload or {"element_id": "space-1", "area_m2": 10.0},
    )


def test_plan_preview_is_deterministic_and_non_mutating() -> None:
    result = preview_sequential_plan("plan", [command("a"), command("b", command_type="LockEntity", payload={"element_id": "building-1"})])
    assert result.executable is True
    assert result.execution_order == ("a", "b")
    assert result.impact_groups == ("cost", "parametric_geometry_intents", "program", "quantities", "validation")
    assert result.fingerprint


def test_plan_preview_fails_closed_for_invalid_command() -> None:
    invalid = command("a", payload={"element_id": "space-1", "area_m2": float("nan")})
    result = preview_sequential_plan("plan", [invalid])
    assert result.executable is False
    assert result.fingerprint is None
    assert result.validation_errors


def test_equivalent_numeric_payloads_have_the_same_plan_fingerprint() -> None:
    integer_area = command("resize", payload={"element_id": "space-1", "area_m2": 10})
    float_area = command("resize", payload={"element_id": "space-1", "area_m2": 10.0})

    integer_preview = preview_sequential_plan("plan", [integer_area])
    float_preview = preview_sequential_plan("plan", [float_area])

    assert integer_preview.executable is True
    assert float_preview.executable is True
    assert integer_preview.fingerprint == float_preview.fingerprint


def test_command_without_canonical_adapter_fails_closed() -> None:
    unsupported = command(
        "move",
        command_type="MoveBuilding",
        payload={"element_id": "building-1", "translation_m": {"x": 1.0, "y": 0.0, "z": 0.0}},
    )
    result = preview_sequential_plan("plan", [unsupported])

    assert result.executable is False
    assert result.fingerprint is None
    assert any("COMMAND_NOT_EXECUTABLE" in error for error in result.validation_errors)
