from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.db.models import User
from app.dependencies import current_user
from app.domains.model.regulatory import RegulatoryRuleSet

from .intent import DesignIntent
from .system_preview import SystemPreview, build_system_preview

router = APIRouter(tags=["architectural-preview"])


@router.post("/projects/{project_id}/design/system-preview")
async def system_preview(
    project_id: str,
    intent: DesignIntent,
    _: User = Depends(current_user),
) -> dict[str, object]:
    """Return a read-only deterministic preview across all architectural layers."""
    if intent.project_id != project_id:
        raise HTTPException(status_code=422, detail="intent project_id must match path project_id")
    result = build_system_preview(intent, regulatory_rules=RegulatoryRuleSet())
    return _serialize(result)


def _serialize(result: SystemPreview) -> dict[str, object]:
    return {
        "project_id": result.intent.project_id,
        "model": result.preview.model.model_dump(mode="json"),
        "geometry": [mesh.model_dump(mode="json") for mesh in result.preview.geometry],
        "scene": {
            "model_hash": result.scene.model_hash,
            "nodes": [node.__dict__ for node in result.scene.nodes],
            "bounds": result.scene.bounds.__dict__,
        },
        "cad": {
            "request": result.cad_job.request.model_dump(mode="json"),
            "provenance": result.cad_job.provenance.__dict__,
        },
        "engineering": {
            "model_hash": result.loads.model_hash,
            "total_factored_load_kn": result.loads.total_factored_load_kn,
            "screening_only": result.loads.is_screening_only,
        },
        "quantities": {
            "model_hash": result.quantities.model_hash,
            "floor_area_m2": result.quantities.floor_area_m2,
            "wall_surface_area_m2": result.quantities.wall_surface_area_m2,
            "slab_volume_m3": result.quantities.slab_volume_m3,
            "conceptual_cost": result.quantities.conceptual_cost,
            "conceptual": result.quantities.is_conceptual,
        },
        "regulatory": {
            "model_hash": result.regulatory.model_hash,
            "passed": result.regulatory.passed,
            "jurisdiction_specific_required": result.regulatory.jurisdiction_specific_required,
            "findings": [finding.__dict__ for finding in result.regulatory.findings],
        },
        "warnings": [warning.model_dump(mode="json") for warning in result.preview.warnings],
        "read_only": True,
    }


__all__ = ["router"]
