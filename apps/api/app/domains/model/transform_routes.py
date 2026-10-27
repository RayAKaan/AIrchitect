from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.db.models import User
from app.dependencies import current_user

from .schemas import ArchitecturalModel
from .transform import TranslateElement, translate_element

router = APIRouter(tags=["model-preview"])


class TransformPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: ArchitecturalModel
    element_id: str = Field(min_length=1, max_length=120)
    dx_m: float = Field(ge=-100_000, le=100_000)
    dy_m: float = Field(ge=-100_000, le=100_000)
    dz_m: float = Field(ge=-100_000, le=100_000)


@router.post("/model/transform-preview")
async def transform_preview(request: TransformPreviewRequest, _: User = Depends(current_user)) -> dict[str, object]:
    try:
        transformed = translate_element(
            request.model,
            TranslateElement(request.element_id, request.dx_m, request.dy_m, request.dz_m),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "read_only": True,
        "source_revision": request.model.revision,
        "result_revision": transformed.revision,
        "model": transformed.model_dump(mode="json"),
    }
