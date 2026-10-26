from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PipelineExecutionRequest:
    workflow_id: str
    project_version_id: str
    source_revision_hash: str
    stages: tuple[str, ...]

    def validate(self) -> None:
        for name, value in (
            ("workflow_id", self.workflow_id),
            ("project_version_id", self.project_version_id),
            ("source_revision_hash", self.source_revision_hash),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not self.stages or any(not stage.strip() for stage in self.stages):
            raise ValueError("stages must contain non-empty stage names")
        if len(set(self.stages)) != len(self.stages):
            raise ValueError("stages must be unique")


class DurableQueue(Protocol):
    async def enqueue(self, request: PipelineExecutionRequest) -> str: ...


async def enqueue_pipeline(queue: DurableQueue, request: PipelineExecutionRequest) -> str:
    """Validate before crossing into the durable worker boundary."""
    request.validate()
    return await queue.enqueue(request)
