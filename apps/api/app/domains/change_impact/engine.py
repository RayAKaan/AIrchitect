from collections import deque
from .schemas import ChangeImpactRequest, ChangeImpactResponse, ImpactedArtifact


def analyze(body: ChangeImpactRequest) -> ChangeImpactResponse:
    """Mark the transitive dependants of changed sources stale, preserving supplied order."""
    nodes = {n.artifact_id: n for n in body.artifacts}
    dependants: dict[str, list[str]] = {key: [] for key in nodes}
    for node in body.artifacts:
        for dependency in node.depends_on:
            dependants[dependency].append(node.artifact_id)

    paths: dict[str, list[str]] = {}
    queue = deque((key, [key]) for key in body.changed_artifact_ids)
    visited_sources = set(body.changed_artifact_ids)
    while queue:
        current, path = queue.popleft()
        for child in dependants[current]:
            if child in visited_sources:
                continue
            visited_sources.add(child)
            paths[child] = path + [child]
            queue.append((child, path + [child]))

    impacted = []
    for node in body.artifacts:
        if node.artifact_id not in paths:
            continue
        impacted.append(ImpactedArtifact(
            artifact_id=node.artifact_id,
            artifact_type=node.artifact_type,
            previous_status=node.status,
            resulting_status="stale",
            reason="A transitive upstream dependency changed; recomputation/review is required.",
            dependency_path=paths[node.artifact_id],
        ))
    unchanged = [n.artifact_id for n in body.artifacts
                 if n.artifact_id not in visited_sources]
    return ChangeImpactResponse(project_id=body.project_id,
        source_revision=body.new_source_revision, impacted=impacted,
        unchanged_artifact_ids=unchanged)
