from typing import Any
from pydantic import BaseModel, Field


class BriefSubmission(BaseModel):
    brief: str = Field(min_length=20, max_length=20000)


class VersionChange(BaseModel):
    changes: dict[str, Any] = Field(min_length=1)
    summary: str = Field(min_length=3, max_length=1000)


class PipelineRun(BaseModel):
    rate_schedule_id: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=200)


class DemoRateScheduleCreate(BaseModel):
    name: str = "Seeded demo feasibility rates"
    geography: str = "Saudi Arabia (demo only)"
    source_date: str = "2026-09-25"
    rates: list[dict[str, Any]] = Field(default_factory=lambda: [
        {"category": "gross_floor_area", "unit": "m2", "low": 1200, "base": 1600, "high": 2100}
    ])
