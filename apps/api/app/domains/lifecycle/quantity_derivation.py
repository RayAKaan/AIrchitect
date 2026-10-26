from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping


@dataclass(frozen=True)
class QuantityLine:
    key: str
    quantity: Decimal
    unit: str
    source_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "quantity": str(self.quantity),
            "unit": self.unit,
            "source_ids": list(self.source_ids),
        }


def derive_space_areas(spaces: Mapping[str, Mapping[str, Any]]) -> tuple[QuantityLine, ...]:
    """Derive stable area quantities from canonical space records."""
    lines: list[QuantityLine] = []
    for space_id in sorted(spaces):
        record = spaces[space_id]
        if not space_id.strip():
            raise ValueError("space ids must not be empty")
        if "area_m2" not in record:
            raise ValueError(f"space {space_id} is missing area_m2")
        try:
            area = Decimal(str(record["area_m2"]))
        except Exception as exc:
            raise ValueError(f"space {space_id} has an invalid area_m2") from exc
        if area < 0:
            raise ValueError(f"space {space_id} has a negative area")
        lines.append(QuantityLine(f"space:{space_id}:area", area, "m2", (space_id,)))
    return tuple(lines)
