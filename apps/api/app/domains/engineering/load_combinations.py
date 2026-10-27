from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoadCase:
    id: str
    kind: str
    magnitude_kpa: float


@dataclass(frozen=True, slots=True)
class LoadCombination:
    id: str
    factors: tuple[tuple[str, float], ...]
    total_factor: float
    label: str


def build_default_combinations(cases: tuple[LoadCase, ...]) -> tuple[LoadCombination, ...]:
    """Return transparent preliminary gravity combinations for screening."""
    ids = {case.id for case in cases}
    if "dead" not in ids or "live" not in ids:
        raise ValueError("LOAD_COMBINATION_INPUTS_INVALID: dead and live cases are required")
    return (
        LoadCombination("ULS-1", (("dead", 1.2), ("live", 1.6)), 2.8, "1.2D + 1.6L"),
        LoadCombination("SLS-1", (("dead", 1.0), ("live", 1.0)), 2.0, "D + L"),
    )
