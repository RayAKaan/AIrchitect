from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json

from app.domains.model import model_hash
from app.domains.model.schemas import ArchitecturalModel
from .model_loads import PreliminaryLoadEnvelope
from .structural_model import StructuralModel


@dataclass(frozen=True, slots=True)
class EngineeringProvenance:
    model_revision: int
    model_hash: str
    geometry_hash: str
    structural_hash: str
    load_hash: str
    result_hash: str
    status: str


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def geometry_hash(model: ArchitecturalModel) -> str:
    payload = {
        "walls": [item.model_dump(mode="json") for item in model.walls],
        "slabs": [item.model_dump(mode="json") for item in model.slabs],
        "doors": [item.model_dump(mode="json") for item in model.doors],
        "windows": [item.model_dump(mode="json") for item in model.windows],
    }
    return _hash(payload)


def structural_hash(model: StructuralModel) -> str:
    return _hash({"nodes": [asdict(item) for item in model.nodes], "members": [asdict(item) for item in model.members]})


def load_hash(loads: PreliminaryLoadEnvelope) -> str:
    return _hash({"assumptions": asdict(loads.assumptions), "levels": [asdict(item) for item in loads.levels], "spaces": [asdict(item) for item in loads.spaces]})


def build_provenance(
    *, model: ArchitecturalModel, structural: StructuralModel, loads: PreliminaryLoadEnvelope,
    result_payload: dict[str, object], status: str,
) -> EngineeringProvenance:
    canonical_hash = model_hash(model)
    return EngineeringProvenance(
        model_revision=model.revision,
        model_hash=canonical_hash,
        geometry_hash=geometry_hash(model),
        structural_hash=structural_hash(structural),
        load_hash=load_hash(loads),
        result_hash=_hash(result_payload),
        status=status,
    )
