from __future__ import annotations

from dataclasses import dataclass

from app.domains.model import model_hash
from app.domains.model.schemas import ArchitecturalModel


@dataclass(frozen=True, slots=True)
class StructuralNode:
    id: str
    x_m: float
    y_m: float
    z_m: float


@dataclass(frozen=True, slots=True)
class StructuralMember:
    id: str
    kind: str
    start_node_id: str
    end_node_id: str
    level_id: str | None
    length_m: float


@dataclass(frozen=True, slots=True)
class StructuralModel:
    model_hash: str
    nodes: tuple[StructuralNode, ...]
    members: tuple[StructuralMember, ...]
    assumptions: tuple[str, ...]
    screening_only: bool = True


def build_structural_model(model: ArchitecturalModel) -> StructuralModel:
    """Derive a deterministic preliminary structural graph from canonical geometry."""
    nodes: dict[str, StructuralNode] = {}
    members: list[StructuralMember] = []
    for wall in sorted(model.walls, key=lambda item: item.id):
        start_id = f"{wall.id}:start"
        end_id = f"{wall.id}:end"
        nodes.setdefault(start_id, StructuralNode(start_id, wall.start.x, wall.start.y, wall.start.z))
        nodes.setdefault(end_id, StructuralNode(end_id, wall.end.x, wall.end.y, wall.end.z))
        dx = wall.end.x - wall.start.x
        dy = wall.end.y - wall.start.y
        members.append(
            StructuralMember(wall.id, "wall_line", start_id, end_id, wall.level_id, (dx * dx + dy * dy) ** 0.5)
        )
    for slab in sorted(model.slabs, key=lambda item: item.id):
        for index, point in enumerate(slab.boundary):
            next_point = slab.boundary[(index + 1) % len(slab.boundary)]
            start_id = f"{slab.id}:p{index}"
            end_id = f"{slab.id}:p{(index + 1) % len(slab.boundary)}"
            nodes.setdefault(start_id, StructuralNode(start_id, point.x, point.y, point.z))
            nodes.setdefault(end_id, StructuralNode(end_id, next_point.x, next_point.y, next_point.z))
            dx = next_point.x - point.x
            dy = next_point.y - point.y
            members.append(
                StructuralMember(
                    f"{slab.id}:edge:{index}",
                    "slab_edge",
                    start_id,
                    end_id,
                    slab.level_id,
                    (dx * dx + dy * dy) ** 0.5,
                )
            )
    return StructuralModel(
        model_hash=model_hash(model),
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        members=tuple(members),
        assumptions=(
            "Walls are represented as line members.",
            "Slab boundaries are represented as perimeter members.",
            "No certified member sizing or code compliance is inferred.",
        ),
    )
