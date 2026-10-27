from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class TranslateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["translate"] = "translate"
    element_id: str = Field(min_length=1, max_length=120)
    dx_m: float = Field(ge=-100_000, le=100_000)
    dy_m: float = Field(ge=-100_000, le=100_000)
    dz_m: float = Field(ge=-100_000, le=100_000)


class RotateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["rotate"] = "rotate"
    element_id: str = Field(min_length=1, max_length=120)
    angle_deg: float = Field(ge=-360_000, le=360_000)


class ResizeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["resize"] = "resize"
    element_id: str = Field(min_length=1, max_length=120)
    scale: float = Field(gt=0, le=100)


EditCommand = Annotated[
    TranslateCommand | RotateCommand | ResizeCommand,
    Field(discriminator="kind"),
]
