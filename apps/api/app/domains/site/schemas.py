from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class SetSiteBoundaryCommand(BaseModel):
    command_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=200)
    base_revision_hash: str | None = Field(default=None, min_length=64, max_length=64)
    boundary: dict[str, Any]
    name: str = Field(default="Site", min_length=1, max_length=200)
    mode: Literal["draft", "commit"] = "commit"
    reason: str = Field(default="Set site boundary", max_length=500)


class SiteRevisionOut(BaseModel):
    site_id: str
    site_revision_id: str
    revision: int
    boundary: dict[str, Any]
    boundary_crs: str
    calculation_crs: str
    area_m2: float
    perimeter_m: float
    content_hash: str
    parent_revision_id: str | None


class ContextFetchOut(BaseModel):
    provider_id: str
    dataset_version: str | None
    feature_count: int
    source_id: str
    snapshot_id: str
    content_hash: str
    status: str


class SiteAnalysisOut(BaseModel):
    analysis_snapshot_id: str
    site_revision_id: str
    source_context_hash: str
    runner_version: str
    status: str
    result: dict[str, Any]


class DiagramOut(BaseModel):
    diagram_snapshot_id: str
    site_revision_id: str
    diagram_type: str
    runner_version: str
    source_context_hash: str | None
    svg: str
    status: str
