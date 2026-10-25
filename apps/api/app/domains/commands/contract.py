from __future__ import annotations

import math
from typing import Any

from .schemas import CommandEnvelope, CommandValidationResult


def _finite_number(value: Any, field: str, *, minimum: float | None = None, maximum: float | None = None) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return f"{field} must be a finite number"
    number = float(value)
    if minimum is not None and number < minimum:
        return f"{field} must be >= {minimum}"
    if maximum is not None and number > maximum:
        return f"{field} must be <= {maximum}"
    return None


def _vector3(value: Any, field: str) -> list[float] | None:
    if isinstance(value, dict):
        raw = [value.get("x", 0), value.get("y", 0), value.get("z", 0)]
    elif isinstance(value, (list, tuple)) and len(value) in (2, 3):
        raw = [*value, 0] if len(value) == 2 else list(value)
    else:
        return None
    result: list[float] = []
    for axis, item in zip(("x", "y", "z"), raw):
        error = _finite_number(item, f"{field}.{axis}")
        if error:
            return None
        result.append(float(item))
    return result


def canonical_payload(command: CommandEnvelope) -> dict[str, Any]:
    payload = dict(command.payload)
    if command.type in {"MoveBuilding", "MoveSpace"}:
        vector = _vector3(payload.get("translation_m"), "translation_m")
        if vector is None:
            raise ValueError("translation_m must be a finite 2D/3D vector")
        payload["translation_m"] = {"x": vector[0], "y": vector[1], "z": vector[2]}
    elif command.type == "RotateBuilding":
        value = payload.get("angle_deg")
        error = _finite_number(value, "angle_deg")
        if error:
            raise ValueError(error)
        payload["angle_deg"] = float(value)
    elif command.type in {"ResizeSpace", "SetProgramArea"}:
        value = payload.get("area_m2")
        error = _finite_number(value, "area_m2", minimum=0.01)
        if error:
            raise ValueError(error)
        payload["area_m2"] = float(value)
    elif command.type == "ChangeSetback":
        value = payload.get("setback_m")
        error = _finite_number(value, "setback_m", minimum=0)
        if error:
            raise ValueError(error)
        payload["setback_m"] = float(value)
    return payload


def validate_payload_contract(command: CommandEnvelope) -> CommandValidationResult:
    try:
        canonical_payload(command)
    except ValueError as exc:
        return CommandValidationResult(valid=False, errors=[str(exc)])
    return CommandValidationResult(valid=True)
