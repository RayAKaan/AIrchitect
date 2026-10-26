from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostInputContract:
    quantity_hash: str
    rate_schedule_hash: str
    currency: str


def require_cost_inputs(value: CostInputContract) -> None:
    fields = {
        "quantity_hash": value.quantity_hash,
        "rate_schedule_hash": value.rate_schedule_hash,
        "currency": value.currency,
    }
    missing = [name for name, item in fields.items() if not item.strip()]
    if missing:
        raise ValueError(f"COST_INPUTS_INVALID: {', '.join(missing)}")
