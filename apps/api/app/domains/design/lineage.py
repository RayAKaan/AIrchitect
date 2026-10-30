from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArtifactVersion, DesignAlternative


async def current_design_input_lineage(session: AsyncSession, version_id: str) -> dict[str, str | None]:
    """Return the exact current program and envelope hashes for a project version."""
    lineage: dict[str, str | None] = {}
    for name, artifact_type in (
        ("program", "architectural_program"),
        ("envelope", "planning_envelope"),
    ):
        artifact = await session.scalar(
            select(ArtifactVersion)
            .where(
                ArtifactVersion.project_version_id == version_id,
                ArtifactVersion.artifact_type == artifact_type,
                ArtifactVersion.status == "current",
            )
            .order_by(ArtifactVersion.version.desc())
            .limit(1)
        )
        lineage[name] = artifact.output_hash if artifact is not None else None
    return lineage


def alternative_is_stale(
    alternative: DesignAlternative | Any,
    current_world_model_hash: str,
    current_lineage: dict[str, str | None],
) -> bool:
    """Compare an alternative against the exact canonical inputs it claims to use."""
    if alternative.input_world_model_hash != current_world_model_hash:
        return True

    provenance = alternative.provenance_json or {}
    recorded_lineage = provenance.get("input_lineage")
    if not isinstance(recorded_lineage, dict):
        recorded_lineage = {
            name: provenance.get(f"{name}_hash")
            for name in ("program", "envelope")
            if f"{name}_hash" in provenance
        }

    has_recorded_lineage = bool(recorded_lineage)
    has_current_lineage = any(value is not None for value in current_lineage.values())
    if not has_recorded_lineage and has_current_lineage:
        return True
    if not has_recorded_lineage:
        return False

    return any(recorded_lineage.get(name) != digest for name, digest in current_lineage.items())
