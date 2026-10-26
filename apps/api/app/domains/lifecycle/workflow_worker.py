from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from .workflow_queue import WorkflowTaskQueue


@dataclass(frozen=True)
class TaskExecutionResult:
    result: dict
    output_hash: str
    artifact_version_id: str | None = None


class WorkflowTaskHandler(Protocol):
    async def __call__(self, session: AsyncSession, task_id: str, payload: dict) -> TaskExecutionResult: ...


@dataclass(frozen=True)
class WorkerRunResult:
    status: str
    task_id: str | None = None
    output_hash: str | None = None
    error_code: str | None = None


class WorkflowTaskHandlerRegistry:
    """Explicit task-handler registry; missing handlers fail closed."""

    def __init__(self, handlers: dict[str, WorkflowTaskHandler] | None = None) -> None:
        self._handlers = dict(handlers or {})

    def register(self, kind: str, handler: WorkflowTaskHandler) -> None:
        normalized = kind.strip()
        if not normalized:
            raise ValueError("workflow task kind must not be empty")
        if normalized in self._handlers:
            raise ValueError(f"workflow task handler already registered: {normalized}")
        self._handlers[normalized] = handler

    def get(self, kind: str) -> WorkflowTaskHandler:
        handler = self._handlers.get(kind)
        if handler is None:
            raise ValueError(f"no workflow task handler registered for {kind}")
        return handler


class WorkflowWorker:
    """Single-iteration worker with claim/execution/completion transaction boundaries."""

    def __init__(
        self,
        *,
        worker_id: str,
        queue: WorkflowTaskQueue | None = None,
        handlers: WorkflowTaskHandlerRegistry | None = None,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        self.worker_id = worker_id
        self.queue = queue or WorkflowTaskQueue()
        self.handlers = handlers or WorkflowTaskHandlerRegistry()

    async def run_once(self, session: AsyncSession) -> WorkerRunResult:
        task = await self.queue.claim_next(session, worker_id=self.worker_id)
        if task is None:
            await session.rollback()
            return WorkerRunResult(status="IDLE")

        task_id = task.id
        task_kind = task.kind
        task_payload = dict(task.payload_json)
        await session.commit()

        try:
            handler = self.handlers.get(task_kind)
            execution = await handler(session, task_id, task_payload)
            await self.queue.complete(
                session,
                task_id,
                worker_id=self.worker_id,
                result=execution.result,
                output_hash=execution.output_hash,
                artifact_version_id=execution.artifact_version_id,
            )
            await session.commit()
            return WorkerRunResult(
                status="SUCCEEDED",
                task_id=task_id,
                output_hash=execution.output_hash,
            )
        except Exception as exc:
            await session.rollback()
            error_code = type(exc).__name__.lower()[:100]
            try:
                await self.queue.fail(
                    session,
                    task_id,
                    worker_id=self.worker_id,
                    error_code=error_code,
                    error_message=str(exc),
                    failure_class="transient",
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            return WorkerRunResult(status="FAILED", task_id=task_id, error_code=error_code)
