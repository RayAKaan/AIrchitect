import pytest

from app.domains.lifecycle.pipeline_execution import PipelineExecutionRequest, enqueue_pipeline


class Queue:
    async def enqueue(self, request: PipelineExecutionRequest) -> str:
        self.request = request
        return "job-1"


@pytest.mark.asyncio
async def test_execution_boundary_validates_before_enqueue() -> None:
    queue = Queue()
    request = PipelineExecutionRequest("w", "v", "source", ("geometry", "cost"))
    assert await enqueue_pipeline(queue, request) == "job-1"
    assert queue.request == request


@pytest.mark.asyncio
async def test_execution_boundary_rejects_duplicate_stages() -> None:
    with pytest.raises(ValueError, match="unique"):
        await enqueue_pipeline(Queue(), PipelineExecutionRequest("w", "v", "s", ("a", "a")))
