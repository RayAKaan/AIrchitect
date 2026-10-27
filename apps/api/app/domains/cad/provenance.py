"""Deterministic provenance for CAD jobs derived from canonical model state."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.domains.cad.protocol import CadJobRequest
from app.domains.model import ArchitecturalModel, model_hash


@dataclass(frozen=True)
class CadInputProvenance:
    project_id: str
    model_revision: int
    model_hash: str
    request_hash: str
    element_ids: tuple[str, ...]


def build_input_provenance(model: ArchitecturalModel, request: CadJobRequest) -> CadInputProvenance:
    """Create the immutable identity used to bind CAD output to canonical state."""
    canonical_hash = model_hash(model)
    payload = request.model_dump(mode="json")
    request_hash = _hash(payload)
    expected_hash = {element.source_reference for element in request.elements}
    if expected_hash != {canonical_hash}:
        raise ValueError("CAD request contains elements from a different canonical model revision")
    return CadInputProvenance(
        project_id=model.project_id,
        model_revision=model.revision,
        model_hash=canonical_hash,
        request_hash=request_hash,
        element_ids=tuple(element.id for element in request.elements),
    )


def _hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["CadInputProvenance", "build_input_provenance"]
