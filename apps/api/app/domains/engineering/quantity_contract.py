from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuantityInputContract:
    geometry_id: str
    geometry_hash: str
    world_model_hash: str
    design_hash: str


def require_quantity_inputs(value: QuantityInputContract) -> None:
    fields = {
        "geometry_id": value.geometry_id,
        "geometry_hash": value.geometry_hash,
        "world_model_hash": value.world_model_hash,
        "design_hash": value.design_hash,
    }
    missing = [name for name, item in fields.items() if not item.strip()]
    if missing:
        raise ValueError(f"QUANTITY_INPUTS_INVALID: {', '.join(missing)}")
