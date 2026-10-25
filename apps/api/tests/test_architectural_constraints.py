from __future__ import annotations

from app.domains.commands.architectural_constraints import validate_architectural_constraints
from app.domains.commands.schemas import CommandEnvelope


def command(command_type: str, payload: dict[str, object]) -> CommandEnvelope:
    return CommandEnvelope(command_id="c1", type=command_type, schema_version=1, project_id="p", version_id="v", base_revision_hash="h", idempotency_key="abcdefgh", payload=payload, reason="test")


def test_setback_cannot_be_negative() -> None:
    errors = validate_architectural_constraints(command("ChangeSetback", {"setback_m": -1}))
    assert errors == ["setback_m must be >= 0"]


def test_space_area_must_be_positive() -> None:
    errors = validate_architectural_constraints(command("ResizeSpace", {"element_id": "s", "area_m2": 0}))
    assert errors == ["area_m2 must be > 0"]


def test_translation_must_be_finite() -> None:
    errors = validate_architectural_constraints(command("MoveBuilding", {"element_id": "b", "translation_m": {"x": float("inf"), "y": 0, "z": 0}}))
    assert errors == ["translation_m.x must be a finite number"]
