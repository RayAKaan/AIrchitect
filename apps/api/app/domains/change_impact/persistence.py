from __future__ import annotations

from collections import deque
from typing import Iterable

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ArtifactDependency, ArtifactVersion, AuditEvent, CadJobRun, CostEstimate,
    DeliverableRecord, DesignAlternative, GeometryArtifact, Project, ProjectVersion,
    QuantityArtifact, RegulatoryEvaluation, StructuralArtifact, ValidationRun,
    WorldModelRevision,
)


def dependency_paths(
    artifact_ids: Iterable[str],
    edges: Iterable[tuple[str, str]],
    changed_ids: Iterable[str],
    *,
    include_roots: bool = False,
) -> dict[str, list[str]]:
    """Return deterministic shortest dependency paths from changed nodes.

    Edges are represented as (dependent_artifact_id, dependency_artifact_id).
    Traversal follows the reverse edge from a changed input to its dependants.
    Cycles terminate because each node is visited at most once.
    """
    known = set(artifact_ids)
    roots = sorted(set(changed_ids))
    if not set(roots) <= known:
        raise ValueError("Changed artifacts must belong to the scoped dependency graph")

    dependants: dict[str, list[str]] = {artifact_id: [] for artifact_id in known}
    for dependent, dependency in edges:
        if dependent in known and dependency in known:
            dependants[dependency].append(dependent)
    for values in dependants.values():
        values.sort()

    paths = {root: [root] for root in roots}
    queue = deque(roots)
    while queue:
        current = queue.popleft()
        for child in dependants[current]:
            if child in paths:
                continue
            paths[child] = [*paths[current], child]
            queue.append(child)

    if include_roots:
        return paths
    return {key: value for key, value in paths.items() if key not in set(roots)}


async def _load_graph(
    session: AsyncSession, project: Project, version: ProjectVersion
) -> tuple[list[ArtifactVersion], list[ArtifactDependency], int]:
    rows = list((await session.scalars(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.project_id == project.id,
            ArtifactVersion.project_version_id == version.id,
        )
        .order_by(ArtifactVersion.created_at, ArtifactVersion.id)
    )).all())
    ids = {row.id for row in rows}
    if not ids:
        return rows, [], 0

    edges = list((await session.scalars(
        select(ArtifactDependency).where(or_(
            ArtifactDependency.artifact_version_id.in_(ids),
            ArtifactDependency.depends_on_artifact_version_id.in_(ids),
        )).order_by(ArtifactDependency.created_at, ArtifactDependency.id)
    )).all())
    valid = [edge for edge in edges
             if edge.artifact_version_id in ids and edge.depends_on_artifact_version_id in ids]
    # A dependency edge crossing a project/version boundary is never traversed.
    return rows, valid, len(edges) - len(valid)


async def dependency_graph_snapshot(
    session: AsyncSession, project: Project, version: ProjectVersion,
    world: WorldModelRevision,
) -> dict:
    rows, edges, rejected_edges = await _load_graph(session, project, version)
    node_ids = {row.id for row in rows}
    dependencies_by_child: dict[str, list[str]] = {key: [] for key in node_ids}
    for edge in edges:
        dependencies_by_child[edge.artifact_version_id].append(edge.depends_on_artifact_version_id)
    nodes = [{
        "artifact_version_id": row.id,
        "artifact_type": row.artifact_type,
        "version": row.version,
        "status": row.status,
        "output_hash": row.output_hash,
        "world_model_revision_id": row.world_model_revision_id,
        "world_model_current": row.world_model_revision_id == world.id,
        "depends_on": sorted(dependencies_by_child[row.id]),
        "immutable_payload": True,
    } for row in rows]
    return {
        "schema_version": "1.0.0",
        "project_id": project.id,
        "project_version_id": version.id,
        "world_model_revision_id": world.id,
        "world_model_hash": world.model_hash,
        "nodes": nodes,
        "edges": [{
            "artifact_version_id": edge.artifact_version_id,
            "depends_on_artifact_version_id": edge.depends_on_artifact_version_id,
            "dependency_kind": edge.dependency_kind,
        } for edge in edges],
        "rejected_cross_scope_edge_count": rejected_edges,
        "integrity": "PASS" if rejected_edges == 0 else "REVIEW_REQUIRED",
    }


async def _mark_domain_rows_stale(session: AsyncSession, artifact_ids: set[str]) -> None:
    if not artifact_ids:
        return
    for model in (
        DesignAlternative, GeometryArtifact, QuantityArtifact, CostEstimate,
        StructuralArtifact, RegulatoryEvaluation, ValidationRun,
    ):
        await session.execute(
            update(model)
            .where(model.artifact_version_id.in_(artifact_ids))
            .values(status="STALE")
        )
    # Deliverables are immutable records; only their lifecycle status changes.
    await session.execute(
        update(DeliverableRecord)
        .where(DeliverableRecord.artifact_id.in_(artifact_ids))
        .values(status="stale")
    )


async def propagate_artifact_change(
    session: AsyncSession,
    *,
    project: Project,
    version: ProjectVersion,
    actor_id: str,
    world: WorldModelRevision,
    changed_artifact_ids: list[str],
    reason: str,
    include_roots: bool = False,
    action: str = "ARTIFACT_CHANGE_PROPAGATED",
) -> dict:
    """Atomically stale the affected artifact lineage and record an audit event."""
    rows, edges, rejected_edges = await _load_graph(session, project, version)
    by_id = {row.id: row for row in rows}
    roots = sorted(set(changed_artifact_ids))
    if not roots or not set(roots) <= set(by_id):
        raise ValueError("Changed artifacts must belong to this project version")

    edge_pairs = [(edge.artifact_version_id, edge.depends_on_artifact_version_id) for edge in edges]
    paths = dependency_paths(by_id, edge_pairs, roots, include_roots=include_roots)
    affected_ids = set(paths)
    previous_status = {artifact_id: by_id[artifact_id].status for artifact_id in affected_ids}
    newly_stale: set[str] = set()
    for artifact_id in affected_ids:
        row = by_id[artifact_id]
        if str(row.status).upper() not in {"STALE", "FAILED", "ERROR", "REJECTED"}:
            row.status = "stale"
            newly_stale.add(artifact_id)

    await _mark_domain_rows_stale(session, newly_stale)
    if action == "WORLD_MODEL_CHANGE_PROPAGATED":
        await session.execute(
            update(CadJobRun)
            .where(
                CadJobRun.project_id == project.id,
                CadJobRun.project_version_id == version.id,
                CadJobRun.input_world_model_hash != (world.model_hash or ""),
                CadJobRun.status.in_(["SUCCEEDED", "SUCCESS", "COMPLETED", "RUNNING"]),
            )
            .values(status="STALE")
        )

    audit = AuditEvent(
        organization_id=project.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        actor_user_id=actor_id,
        action=action,
        resource_type="world_model_revision" if action == "WORLD_MODEL_CHANGE_PROPAGATED" else "artifact_dependency_graph",
        resource_id=world.id,
        metadata_json={
            "world_model_hash": world.model_hash,
            "changed_artifact_ids": roots,
            "affected_artifact_ids": sorted(affected_ids),
            "newly_stale_artifact_ids": sorted(newly_stale),
            "dependency_paths": paths,
            "reason": reason,
            "rejected_cross_scope_edge_count": rejected_edges,
        },
    )
    session.add(audit)
    return {
        "project_id": project.id,
        "project_version_id": version.id,
        "world_model_revision_id": world.id,
        "world_model_hash": world.model_hash,
        "changed_artifact_ids": roots,
        "affected": [{
            "artifact_version_id": artifact_id,
            "artifact_type": by_id[artifact_id].artifact_type,
            "previous_status": previous_status[artifact_id],
            "resulting_status": "stale" if artifact_id in newly_stale or str(previous_status[artifact_id]).upper() == "STALE" else previous_status[artifact_id],
            "dependency_path": paths[artifact_id],
        } for artifact_id in sorted(affected_ids, key=lambda item: (len(paths[item]), item))],
        "newly_stale_artifact_ids": sorted(newly_stale),
        "rejected_cross_scope_edge_count": rejected_edges,
        "atomic": True,
        "recomputation_scheduled": False,
        "reason": reason,
    }


async def propagate_world_model_change(
    session: AsyncSession,
    *,
    project: Project,
    version: ProjectVersion,
    actor_id: str,
    previous_world: WorldModelRevision,
    current_world: WorldModelRevision,
) -> dict | None:
    """Invalidate artifacts bound to a superseded canonical World Model hash."""
    if previous_world.model_hash == current_world.model_hash:
        return None
    rows, _, _ = await _load_graph(session, project, version)
    roots = [
        row.id for row in rows
        if row.world_model_revision_id != current_world.id
    ]
    if not roots:
        # CAD runs may exist before the canonical artifact registry was populated.
        await session.execute(
            update(CadJobRun)
            .where(
                CadJobRun.project_id == project.id,
                CadJobRun.project_version_id == version.id,
                CadJobRun.input_world_model_hash != (current_world.model_hash or ""),
                CadJobRun.status.in_(["SUCCEEDED", "SUCCESS", "COMPLETED", "RUNNING"]),
            )
            .values(status="STALE")
        )
        return None
    return await propagate_artifact_change(
        session,
        project=project,
        version=version,
        actor_id=actor_id,
        world=current_world,
        changed_artifact_ids=roots,
        reason="Canonical World Model hash changed; dependent calculations and exports must be recomputed or reviewed.",
        include_roots=True,
        action="WORLD_MODEL_CHANGE_PROPAGATED",
    )
