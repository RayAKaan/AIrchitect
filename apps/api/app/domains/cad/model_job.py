"""Application boundary for scheduling CAD from canonical architectural state."""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.cad.model_adapter import build_cad_request
from app.domains.cad.provenance import CadInputProvenance, build_input_provenance
from app.domains.cad.protocol import CadJobRequest
from app.domains.model import ArchitecturalModel


@dataclass(frozen=True)
class CanonicalCadJob:
    request: CadJobRequest
    provenance: CadInputProvenance


def build_canonical_cad_job(
    model: ArchitecturalModel,
    *,
    job_id: str,
    alternative_ref: str = "",
    project_name: str = "AIrchitect Project",
) -> CanonicalCadJob:
    """Build the complete immutable input passed to the CAD orchestration layer."""
    if not job_id.strip():
        raise ValueError("job_id must not be blank")
    request = build_cad_request(
        model,
        job_id=job_id,
        alternative_ref=alternative_ref,
        project_name=project_name,
    )
    provenance = build_input_provenance(model, request)
    return CanonicalCadJob(request=request, provenance=provenance)


__all__ = ["CanonicalCadJob", "build_canonical_cad_job"]
