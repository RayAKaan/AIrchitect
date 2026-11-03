from __future__ import annotations

from .schemas import CommandEnvelope


IMPACT_GROUPS: dict[str, tuple[str, ...]] = {
    "MoveBuilding": ("design_alternatives", "spatial_layout", "spatial_topology", "architectural_elements", "architectural_constraints", "parametric_geometry_intents", "quantities", "cost", "validation"),
    "RotateBuilding": ("design_alternatives", "spatial_layout", "spatial_topology", "architectural_elements", "architectural_constraints", "parametric_geometry_intents", "quantities", "cost", "validation"),
    "ChangeSetback": ("planning_envelope", "design_alternatives", "spatial_layout", "spatial_topology", "architectural_elements", "architectural_constraints", "parametric_geometry_intents", "validation"),
    "AddLevel": ("program", "design_alternatives", "spatial_layout", "spatial_topology", "architectural_elements", "architectural_constraints", "parametric_geometry_intents", "quantities", "cost", "structural_review", "regulatory_review", "validation"),
    "ResizeSpace": ("program", "spatial_layout", "spatial_topology", "architectural_elements", "architectural_constraints", "parametric_geometry_intents", "quantities", "cost", "validation"),
    "MoveSpace": ("spatial_layout", "spatial_topology", "architectural_elements", "architectural_constraints", "parametric_geometry_intents", "validation"),
    "SetProgramArea": ("program", "design_alternatives", "spatial_layout", "spatial_topology", "architectural_elements", "architectural_constraints", "parametric_geometry_intents", "quantities", "cost"),
    "LockEntity": (),
    # Preview and plan APIs do not load the undo/redo target history. Use a
    # conservative impact set there; execution narrows this to the target event.
    "Undo": ("planning_envelope", "feasibility", "program", "design_alternatives", "spatial_layout", "spatial_topology", "architectural_elements", "architectural_constraints", "parametric_geometry_intents", "quantities", "cost", "structural_review", "regulatory_review", "validation"),
    "Redo": ("planning_envelope", "feasibility", "program", "design_alternatives", "spatial_layout", "spatial_topology", "architectural_elements", "architectural_constraints", "parametric_geometry_intents", "quantities", "cost", "structural_review", "regulatory_review", "validation"),
}


def impact_for(command: CommandEnvelope) -> list[str]:
    """Return deterministic downstream artifact groups for a validated command."""
    return list(IMPACT_GROUPS.get(command.type, ()))
