"""One deterministic preview pipeline spanning design, model, CAD and analysis."""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.cad.model_job import CanonicalCadJob, build_canonical_cad_job
from app.domains.engineering.model_loads import PreliminaryLoadEnvelope, derive_preliminary_loads
from app.domains.estimates.model_quantities import ModelQuantities, derive_model_quantities
from app.domains.geometry.scene import ModelScene, build_model_scene
from app.domains.model.regulatory import RegulatoryRuleSet, RegulatoryScreening, screen_model
from app.domains.model.schemas import ArchitecturalModel

from .intent import DesignIntent
from .preview import ModelPreview, build_model_preview


@dataclass(frozen=True)
class SystemPreview:
    intent: DesignIntent
    preview: ModelPreview
    scene: ModelScene
    cad_job: CanonicalCadJob
    loads: PreliminaryLoadEnvelope
    quantities: ModelQuantities
    regulatory: RegulatoryScreening


def build_system_preview(
    intent: DesignIntent,
    *,
    regulatory_rules: RegulatoryRuleSet | None = None,
) -> SystemPreview:
    """Execute the complete deterministic preview chain without committing state."""
    preview = build_model_preview(intent)
    model: ArchitecturalModel = preview.model
    scene = build_model_scene(model)
    cad_job = build_canonical_cad_job(model, job_id=f"preview:{model.revision}:{model.project_id}")
    loads = derive_preliminary_loads(model)
    quantities = derive_model_quantities(model)
    regulatory = screen_model(model, regulatory_rules or RegulatoryRuleSet())
    return SystemPreview(
        intent=intent,
        preview=preview,
        scene=scene,
        cad_job=cad_job,
        loads=loads,
        quantities=quantities,
        regulatory=regulatory,
    )


__all__ = ["SystemPreview", "build_system_preview"]
