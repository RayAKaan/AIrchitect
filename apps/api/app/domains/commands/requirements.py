from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandRequirement:
    name: str
    required_fields: tuple[str, ...]
    description: str


COMMAND_REQUIREMENTS: dict[str, CommandRequirement] = {
    "SetSiteBoundary": CommandRequirement("SetSiteBoundary", ("site_id", "boundary"), "Replace the canonical site boundary."),
    "MoveBuilding": CommandRequirement("MoveBuilding", ("element_id", "translation_m"), "Translate a building."),
    "RotateBuilding": CommandRequirement("RotateBuilding", ("element_id", "angle_deg"), "Rotate a building."),
    "ChangeSetback": CommandRequirement("ChangeSetback", ("setback_m",), "Change the planning setback."),
    "AddLevel": CommandRequirement("AddLevel", ("building_id", "elevation_m"), "Add a building level."),
    "ResizeSpace": CommandRequirement("ResizeSpace", ("element_id", "area_m2"), "Change a space target area."),
    "MoveSpace": CommandRequirement("MoveSpace", ("element_id", "translation_m"), "Translate a space."),
    "SetProgramArea": CommandRequirement("SetProgramArea", ("space_type", "area_m2"), "Set a program area target."),
    "LockEntity": CommandRequirement("LockEntity", ("element_id",), "Lock an entity against mutation."),
    "Undo": CommandRequirement("Undo", (), "Create a new revision reversing a prior command."),
}


def requirements_for(command_type: str) -> CommandRequirement | None:
    return COMMAND_REQUIREMENTS.get(command_type)
