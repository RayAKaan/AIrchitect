from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactVersion
from app.db.regeneration_job_models import RegenerationJobRecord
from app.db.regeneration_models import RegenerationStateRecord

from .regeneration_executor import RegenerationHandlerRegistry, RegenerationInput, RegenerationOutput
from .regeneration_queue import assert_job_lease
from .regeneration_repository import RegenerationStateRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RegenerationService:
    """Execute and atomically commit one claimed regeneration job."""

    def __init__(
        self,
        handlers: RegenerationHandlerRegistry | None = None,
        states: RegenerationStateRepository | None = None,
    ) -> None:
        self._handlers = handlers or RegenerationHandlerRegistry()
        self._states = states or RegenerationStateRepository()

    async def execute_job(
        self,
        session: AsyncSession,
        job_id: str,
        *,
        worker_id: str,
        attempt_count: int,
    ) -> RegenerationOutput:
        job = await self._locked_job(session, job_id)
        assert_job_lease(job, worker_id, attempt_count)
        state = await self._locked_state(session, job.regeneration_state_id)
        if state.status != "RUNNING":
            raise ValueError(f"regeneration state is not RUNNING: {state.status}")
        if state.source_revision_hash != job.source_revision_hash:
            raise ValueError("job and regeneration state revisions do not match")

        artifact = await self._locked_artifact(session, job.artifact_version_id)
        if artifact.status != "stale":
            raise ValueError(f"artifact is not stale: {artifact.status}")

        output = self._handlers.execute(
            RegenerationInput(
                artifact_type=artifact.artifact_type,
                source_revision_hash=job.source_revision_hash,
                payload=artifact.payload_json,
            )
        )
        self._commit_output(artifact, job, output)
        await self._states.transition(
            session,
            state,
            "SUCCEEDED",
        )
        await self._states.transition(
            session,
            state,
            "CURRENT",
            output_revision_hash=job.source_revision_hash,
        )
        job.status = "SUCCEEDED"
        job.completed_at = _now()
        job.locked_at = None
        job.locked_by = None
        await session.flush()
        return output

    @staticmethod
    async def _locked_job(session: AsyncSession, job_id: str) -> RegenerationJobRecord:
        result = await session.execute(
            select(RegenerationJobRecord)
            .where(RegenerationJobRecord.id == job_id)
            .with_for_update()
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise ValueError("regeneration job not found")
        return job

    @staticmethod
    async def _locked_state(session: AsyncSession, state_id: str) -> RegenerationStateRecord:
        result = await session.execute(
            select(RegenerationStateRecord)
            .where(RegenerationStateRecord.id == state_id)
            .with_for_update()
        )
        state = result.scalar_one_or_none()
        if state is None:
            raise ValueError("regeneration state not found")
        return state

    @staticmethod
    async def _locked_artifact(session: AsyncSession, artifact_id: str) -> ArtifactVersion:
        result = await session.execute(
            select(ArtifactVersion)
            .where(ArtifactVersion.id == artifact_id)
            .with_for_update()
        )
        artifact = result.scalar_one_or_none()
        if artifact is None:
            raise ValueError("artifact version not found")
        return artifact

    @staticmethod
    def _commit_output(
        artifact: ArtifactVersion,
        job: RegenerationJobRecord,
        output: RegenerationOutput,
    ) -> None:
        if output.artifact_type != artifact.artifact_type:
            raise ValueError("regeneration output artifact type mismatch")
        artifact.version += 1
        artifact.status = "current"
        artifact.payload_json = output.payload
        artifact.output_hash = output.output_hash
        artifact.provenance_json = {
            **artifact.provenance_json,
            "regeneration_job_id": job.id,
            "source_revision_hash": job.source_revision_hash,
            "engine_version": output.engine_version,
            "regenerated_at": _now().isoformat(),
        }
