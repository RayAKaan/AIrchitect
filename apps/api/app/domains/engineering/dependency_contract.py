from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineeringDependency:
    geometry_id: str
    geometry_hash: str
    quantity_hash: str
    structural_input_hash: str
    regulatory_input_hash: str


def require_canonical_engineering_chain(value: EngineeringDependency) -> None:
    fields = {
        "geometry_id": value.geometry_id,
        "geometry_hash": value.geometry_hash,
        "quantity_hash": value.quantity_hash,
        "structural_input_hash": value.structural_input_hash,
        "regulatory_input_hash": value.regulatory_input_hash,
    }
    missing = [name for name, item in fields.items() if not item.strip()]
    if missing:
        raise ValueError(f"ENGINEERING_DEPENDENCY_INCOMPLETE: {', '.join(missing)}")
