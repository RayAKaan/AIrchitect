from __future__ import annotations

from dataclasses import dataclass

from .structural_model import StructuralModel


@dataclass(frozen=True, slots=True)
class ScenePrimitive:
    id: str
    primitive: str
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    semantic_type: str


def build_structural_scene(model: StructuralModel) -> tuple[ScenePrimitive, ...]:
    """Create renderer-neutral engineering primitives tied to structural member IDs."""
    nodes = {node.id: node for node in model.nodes}
    return tuple(
        ScenePrimitive(
            member.id,
            "line",
            (nodes[member.start_node_id].x_m, nodes[member.start_node_id].y_m, nodes[member.start_node_id].z_m),
            (nodes[member.end_node_id].x_m, nodes[member.end_node_id].y_m, nodes[member.end_node_id].z_m),
            member.kind,
        )
        for member in model.members
    )
