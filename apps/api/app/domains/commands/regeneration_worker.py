from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from .regeneration_queue import RegenerationQueue
from .regeneration_service import RegenerationService


@dataclass(frozen=True)
class WorkerRunResult:
    status: str
    job_id: str | None = None
    output_hash: str | None = None
    error_code: str | None = None


class RegenerationWorker:
    """Single-iteration worker; process supervision supplies the outer loop."""

    def __init__(
        self,
        *,
        worker_id: str,
        queue: RegenerationQueue | None = None,
        service: RegenerationService | None = None,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        self.worker_id = worker_id
        self.queue = queue or RegenerationQueue()
        self.service = service or RegenerationService()

    async def run_once(self, session: AsyncSession) -> WorkerRunResult:
        job = await self.queue.claim_next(session, worker_id=self.worker_id)
        if job is None:
            await session.rollback()
            return WorkerRunResult(status="IDLE")

        # The lease must survive execution. Claim and execution therefore have
        # separate transactions: another worker must never see the job as queued
        # while this worker is executing it.
        job_id = job.id
        await session.commit()
        try:
            output = await self.service.execute_job(session, job_id)
            await session.commit()
            return WorkerRunResult(status="SUCCEEDED", job_id=job_id, output_hash=output.output_hash)
        except Exception as exc:
            # The execution service deliberately owns no commit. Roll back all
            # partial output writes before recording the failure in a fresh
            # transaction, so a failed attempt cannot publish a half-written
            # artifact while simultaneously becoming retryable.
            await session.rollback()
            error_code = type(exc).__name__.lower()[:100]
            try:
                await self.queue.fail_by_id(
                    session,
                    job_id,
                    error_code=error_code,
                    error_message=str(exc),
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            return WorkerRunResult(status="FAILED", job_id=job_id, error_code=error_code)
