import pytest
from pydantic import ValidationError

from app.domains.model.commands import ModelCommand, command_fingerprint


def test_command_fingerprint_is_stable() -> None:
    command = ModelCommand(
        command_id="cmd-1",
        operation="create",
        element_type="wall",
        element_id="wall-1",
        expected_revision=3,
        payload={"height_m": 3, "thickness_m": 0.2},
    )
    equivalent = ModelCommand.model_validate(command.model_dump())
    assert command_fingerprint(command) == command_fingerprint(equivalent)


def test_delete_command_cannot_carry_payload() -> None:
    with pytest.raises(ValidationError, match="delete commands cannot carry a payload"):
        ModelCommand(
            command_id="cmd-1",
            operation="delete",
            element_type="wall",
            element_id="wall-1",
            expected_revision=3,
            payload={"reason": "obsolete"},
        )


def test_create_command_requires_payload() -> None:
    with pytest.raises(ValidationError, match="create commands require a payload"):
        ModelCommand(
            command_id="cmd-1",
            operation="create",
            element_type="wall",
            element_id="wall-1",
            expected_revision=3,
        )
