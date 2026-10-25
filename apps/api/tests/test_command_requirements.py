from __future__ import annotations

from app.domains.commands.requirements import requirements_for


def test_all_builtin_commands_have_explicit_requirements() -> None:
    expected = {
        "SetSiteBoundary", "MoveBuilding", "RotateBuilding", "ChangeSetback",
        "AddLevel", "ResizeSpace", "MoveSpace", "SetProgramArea", "LockEntity", "Undo",
    }
    assert set(__import__("app.domains.commands.builtins", fromlist=["COMMANDS"]).COMMANDS[i][0] for i in range(10)) == expected
    assert all(requirements_for(name) is not None for name in expected)


def test_unknown_command_fails_closed() -> None:
    assert requirements_for("InventBuilding") is None


def test_requirements_are_immutable_contracts() -> None:
    requirement = requirements_for("MoveBuilding")
    assert requirement is not None
    assert requirement.required_fields == ("element_id", "translation_m")
