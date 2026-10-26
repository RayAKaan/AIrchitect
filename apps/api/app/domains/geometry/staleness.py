from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeometryStaleness:
    geometry_hash: str
    current_world_model_hash: str
    geometry_world_model_hash: str
    current_design_hash: str
    geometry_design_hash: str

    @property
    def stale(self) -> bool:
        return (
            self.current_world_model_hash != self.geometry_world_model_hash
            or self.current_design_hash != self.geometry_design_hash
        )

    @property
    def reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.current_world_model_hash != self.geometry_world_model_hash:
            reasons.append("WORLD_MODEL_CHANGED")
        if self.current_design_hash != self.geometry_design_hash:
            reasons.append("DESIGN_CHANGED")
        return tuple(reasons)


def require_current_geometry(value: GeometryStaleness) -> None:
    if value.stale:
        raise ValueError("GEOMETRY_STALE: " + ",".join(value.reasons))
