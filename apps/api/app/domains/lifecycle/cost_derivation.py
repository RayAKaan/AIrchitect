from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable


_CURRENCY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class CostLine:
    key: str
    quantity: Decimal
    unit_rate: Decimal
    amount: Decimal
    currency: str
    source_key: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "quantity": str(self.quantity),
            "unit_rate": str(self.unit_rate),
            "amount": str(self.amount),
            "currency": self.currency,
            "source_key": self.source_key,
        }


def derive_costs(
    quantities: Iterable[tuple[str, Decimal]],
    rates: dict[str, Decimal],
    *,
    currency: str,
) -> tuple[CostLine, ...]:
    if not currency.strip():
        raise ValueError("currency must not be empty")
    normalized = sorted(quantities, key=lambda item: item[0])
    lines: list[CostLine] = []
    for key, quantity in normalized:
        if key not in rates:
            raise ValueError(f"missing unit rate for {key}")
        rate = Decimal(rates[key])
        quantity = Decimal(quantity)
        if quantity < 0 or rate < 0:
            raise ValueError("quantities and rates must not be negative")
        amount = (quantity * rate).quantize(_CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)
        lines.append(CostLine(key, quantity, rate, amount, currency, key))
    return tuple(lines)
