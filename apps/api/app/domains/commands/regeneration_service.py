from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactDependency, ArtifactVersion, Project, ProjectVersion, WorldModelRevision
from app.db.regeneration_job_models import RegenerationJobRecord
from app.db.regeneration_models import RegenerationStateRecord
from app.domains.lifecycle.artifact_rebinding import rebind_artifact

from .regeneration_executor import RegenerationHandlerRegistry, RegenerationInput, RegenerationOutput
from .regeneration_queue import assert_job_lease
from .regeneration_repository import RegenerationStateRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RegenerationService:
    """Execute and atomically publish one immutable artifact successor."""

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

        dependencies = await self._current_dependencies(session, artifact)
        dependency_snapshots = {
            dependency.artifact_type: {
                "output_hash": dependency.output_hash,
                "payload": dependency.payload_json,
            }
            for dependency in dependencies
        }
        output = self._handlers.execute(
            RegenerationInput(
                artifact_type=artifact.artifact_type,
                source_revision_hash=job.source_revision_hash,
                payload=artifact.payload_json,
                dependencies=dependency_snapshots,
            )
        )
        successor = await self._publish_successor(
            session, artifact, job, output, dependencies=dependencies
        )
        await self._states.transition(session, state, "SUCCEEDED")

        successor_state = await self._states.get_for_update(session, successor.id)
        if successor_state is None:
            await self._states.create_current(
                session,
                organization_id=job.organization_id,
                project_id=job.project_id,
                project_version_id=job.project_version_id,
                artifact_version_id=successor.id,
                source_revision_hash=job.source_revision_hash,
                generation_key=f"{successor.artifact_type}:{job.source_revision_hash}",
            )
        elif (
            successor_state.status != "CURRENT"
            or successor_state.source_revision_hash != job.source_revision_hash
            or successor_state.output_revision_hash != job.source_revision_hash
        ):
            raise ValueError("successor artifact has a conflicting regeneration state")

        job.status = "SUCCEEDED"
        job.completed_at = _now()
        job.locked_at = None
        job.locked_by = None
        await session.flush()
        return output

    async def _publish_successor(
        self,
        session: AsyncSession,
        artifact: ArtifactVersion,
        job: RegenerationJobRecord,
        output: RegenerationOutput,
        *,
        dependencies: list[ArtifactVersion],
    ) -> ArtifactVersion:
        if output.artifact_type != artifact.artifact_type:
            raise ValueError("regeneration output artifact type mismatch")
        if output.source_revision_hash != job.source_revision_hash:
            raise ValueError("regeneration output source revision mismatch")

        project = await session.get(Project, job.project_id)
        version = await session.get(ProjectVersion, job.project_version_id)
        if project is None or version is None:
            raise ValueError("regeneration project or project version not found")
        world_result = await session.execute(
            select(WorldModelRevision)
            .where(
                WorldModelRevision.project_id == job.project_id,
                WorldModelRevision.project_version_id == job.project_version_id,
                WorldModelRevision.model_hash == job.source_revision_hash,
            )
            .order_by(WorldModelRevision.revision.desc())
            .limit(1)
        )
        world = world_result.scalar_one_or_none()
        if world is None:
            raise ValueError("regeneration source world-model revision not found")

        return await rebind_artifact(
            session,
            project=project,
            version=version,
            world=world,
            previous_artifact_id=artifact.id,
            actor=artifact.created_by,
            payload=output.payload,
            source_revision_hash=job.source_revision_hash,
            dependencies=dependencies,
            engine_version=output.engine_version,
            output_hash=output.output_hash,
        )

    @staticmethod
    async def _current_dependencies(
        session: AsyncSession,
        artifact: ArtifactVersion,
    ) -> list[ArtifactVersion]:
        edge_result = await session.scalars(
            select(ArtifactDependency)
            .where(ArtifactDependency.artifact_version_id == artifact.id)
            .order_by(ArtifactDependency.id)
        )
        dependencies: list[ArtifactVersion] = []
        seen: set[str] = set()
        for edge in edge_result:
            previous = await session.get(ArtifactVersion, edge.depends_on_artifact_version_id)
            if previous is None:
                raise ValueError("regeneration dependency artifact not found")
            current_result = await session.execute(
                select(ArtifactVersion)
                .where(
                    ArtifactVersion.project_version_id == artifact.project_version_id,
                    ArtifactVersion.artifact_type == previous.artifact_type,
                    ArtifactVersion.alternative_id == previous.alternative_id,
                    ArtifactVersion.status == "current",
                )
                .order_by(ArtifactVersion.version.desc())
                .limit(1)
            )
            current = current_result.scalar_one_or_none()
            if current is None:
                raise ValueError(
                    f"REGENERATION_DEPENDENCY_NOT_CURRENT: {previous.artifact_type} "
                    f"for alternative {previous.alternative_id or 'project'}"
                )
            if current.id not in seen:
                dependencies.append(current)
                seen.add(current.id)
        return dependencies

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
