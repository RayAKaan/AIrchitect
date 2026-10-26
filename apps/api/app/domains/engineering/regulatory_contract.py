from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegulatoryInputContract:
    geometry_hash: str
    quantity_hash: str
    world_model_hash: str
    design_hash: str
    ruleset_hash: str


def require_regulatory_inputs(value: RegulatoryInputContract) -> None:
    fields = {
        "geometry_hash": value.geometry_hash,
        "quantity_hash": value.quantity_hash,
        "world_model_hash": value.world_model_hash,
        "design_hash": value.design_hash,
        "ruleset_hash": value.ruleset_hash,
    }
    missing = [name for name, item in fields.items() if not item.strip()]
    if missing:
        raise ValueError(f"REGULATORY_INPUTS_INVALID: {', '.join(missing)}")
