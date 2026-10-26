from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StructuralInputContract:
    geometry_hash: str
    quantity_hash: str
    world_model_hash: str
    design_hash: str


def require_structural_inputs(value: StructuralInputContract) -> None:
    fields = {
        "geometry_hash": value.geometry_hash,
        "quantity_hash": value.quantity_hash,
        "world_model_hash": value.world_model_hash,
        "design_hash": value.design_hash,
    }
    missing = [name for name, item in fields.items() if not item.strip()]
    if missing:
        raise ValueError(f"STRUCTURAL_INPUTS_INVALID: {', '.join(missing)}")
