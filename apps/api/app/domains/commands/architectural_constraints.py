from __future__ import annotations

import math
from typing import Any

from .schemas import CommandEnvelope

from app.domains.program.service import CATALOG


def validate_architectural_constraints(command: CommandEnvelope) -> list[str]:
    """Validate command-level invariants before model-specific mutation.

    This layer intentionally knows nothing about geometry or planning law. It only
    rejects mathematically invalid architectural inputs; project-specific rules
    belong to later constraint providers.
    """
    payload: dict[str, Any] = command.payload
    errors: list[str] = []

    def finite_number(name: str, *, minimum: float | None = None, exclusive_minimum: bool = False) -> None:
        value = payload.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
            errors.append(f"{name} must be a finite number")
            return
        numeric = float(value)
        if minimum is not None and ((numeric <= minimum) if exclusive_minimum else (numeric < minimum)):
            comparator = ">" if exclusive_minimum else ">="
            errors.append(f"{name} must be {comparator} {minimum}")

    if command.type == "ChangeSetback":
        finite_number("setback_m", minimum=0)
    elif command.type == "ResizeSpace":
        finite_number("area_m2", minimum=0, exclusive_minimum=True)
    elif command.type == "SetProgramArea":
        finite_number("area_m2", minimum=0, exclusive_minimum=True)
        space_type = payload.get("space_type")
        known_space_types = {
            name.lower().replace(" ", "_")
            for catalog in CATALOG.values()
            for name, _, _ in catalog
        }
        if not isinstance(space_type, str) or space_type not in known_space_types:
            errors.append("space_type must identify a known program space type")
    elif command.type == "AddLevel":
        finite_number("elevation_m")
    elif command.type == "RotateBuilding":
        finite_number("angle_deg")
    elif command.type in {"MoveBuilding", "MoveSpace"}:
        vector = payload.get("translation_m")
        if not isinstance(vector, dict):
            errors.append("translation_m must be an object")
        else:
            for axis in ("x", "y", "z"):
                value = vector.get(axis)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
                    errors.append(f"translation_m.{axis} must be a finite number")
    return errors
