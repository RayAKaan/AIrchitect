from __future__ import annotations

from .schemas import CommandEnvelope


IMPACT_GROUPS: dict[str, tuple[str, ...]] = {
    "MoveBuilding": ("parametric_geometry_intents", "quantities", "cost", "validation"),
    "RotateBuilding": ("parametric_geometry_intents", "quantities", "cost", "validation"),
    "ChangeSetback": ("planning_envelope", "design_alternatives", "parametric_geometry_intents", "validation"),
    "AddLevel": ("program", "parametric_geometry_intents", "quantities", "cost", "structural_review", "validation"),
    "ResizeSpace": ("program", "parametric_geometry_intents", "quantities", "cost", "validation"),
    "MoveSpace": ("parametric_geometry_intents", "quantities", "validation"),
    "SetProgramArea": ("program", "design_alternatives", "parametric_geometry_intents", "quantities", "cost"),
    "LockEntity": (),
}


def impact_for(command: CommandEnvelope) -> list[str]:
    """Return deterministic downstream artifact groups for a validated command."""
    return list(IMPACT_GROUPS.get(command.type, ()))
