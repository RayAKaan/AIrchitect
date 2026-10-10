from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.db.models import ArtifactDependency, ArtifactVersion, AuditEvent


async def _workspace(api, suffix: str):
    registration = await api.post("/api/v1/auth/register", json={
        "email": f"phase27-{suffix}-{uuid.uuid4().hex}@example.com",
        "name": "Phase 27 Tester",
        "password": "a-very-secure-password",
        "organization_name": f"Phase 27 Org {suffix}",
    })
    assert registration.status_code == 201, registration.text
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    organization = (await api.get("/api/v1/organizations", headers=headers)).json()[0]
    project_response = await api.post("/api/v1/projects", headers=headers, json={
        "organization_id": organization["id"],
        "name": f"Phase 27 Project {suffix}",
        "description": "Dependency propagation integration test",
        "building_type": "commercial_retail",
        "location": "Riyadh, Saudi Arabia",
    })
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()
    version_id = project["current_version_id"]
    world_response = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/world-model",
        headers=headers,
    )
    assert world_response.status_code == 200, world_response.text
    world = world_response.json()["world_model_revision"]
    me = (await api.get("/api/v1/auth/me", headers=headers)).json()
    return headers, project, version_id, world, me["id"]


async def _seed_graph(db, *, project, version_id, world, actor_id):
    ids = ["phase27-source", "phase27-geometry", "phase27-quantity", "phase27-cost", "phase27-unrelated"]
    types = ["source_input", "geometry", "quantity", "cost", "note"]
    async with db() as session:
        for artifact_id, artifact_type in zip(ids, types, strict=True):
            session.add(ArtifactVersion(
                id=artifact_id,
                organization_id=project["organization_id"],
                project_id=project["id"],
                project_version_id=version_id,
                world_model_revision_id=world["id"],
                artifact_type=artifact_type,
                version=1,
                status="current",
                provenance_json={"test": "phase27"},
                input_references_json=[],
                output_hash=("a" * 64),
                payload_json={"artifact_type": artifact_type},
                created_by=actor_id,
            ))
        await session.flush()
        for dependent, dependency in [
            ("phase27-geometry", "phase27-source"),
            ("phase27-quantity", "phase27-geometry"),
            ("phase27-cost", "phase27-quantity"),
        ]:
            session.add(ArtifactDependency(
                artifact_version_id=dependent,
                depends_on_artifact_version_id=dependency,
                dependency_kind="input",
            ))
        await session.commit()
    return ids


@pytest.mark.asyncio
async def test_persisted_graph_and_explicit_propagation_are_atomic_and_scoped(api, db):
    headers, project, version_id, world, actor_id = await _workspace(api, "explicit")
    ids = await _seed_graph(db, project=project, version_id=version_id, world=world, actor_id=actor_id)

    graph_response = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/change-impact/graph",
        headers=headers,
    )
    assert graph_response.status_code == 200, graph_response.text
    graph = graph_response.json()
    assert len(graph["nodes"]) == 5
    assert len(graph["edges"]) == 3
    assert graph["integrity"] == "PASS"

    response = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/change-impact/propagate",
        headers=headers,
        json={
            "changed_artifact_ids": [ids[0]],
            "expected_world_model_hash": world["model_hash"],
            "reason": "Source dimensions changed during review",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["atomic"] is True
    assert payload["recomputation_scheduled"] is False
    assert payload["newly_stale_artifact_ids"] == sorted(ids[1:4])
    assert payload["affected"][0]["dependency_path"] == [ids[0], ids[1]]
    assert payload["affected"][-1]["dependency_path"] == [ids[0], ids[1], ids[2], ids[3]]

    async with db() as session:
        statuses = {
            row.id: row.status for row in (
                await session.scalars(select(ArtifactVersion).where(ArtifactVersion.id.in_(ids)))
            ).all()
        }
        audit_rows = list((await session.scalars(
            select(AuditEvent).where(
                AuditEvent.project_id == project["id"],
                AuditEvent.action == "ARTIFACT_CHANGE_PROPAGATED",
            )
        )).all())
    assert statuses[ids[0]] == "current"
    assert statuses[ids[1]] == statuses[ids[2]] == statuses[ids[3]] == "stale"
    assert statuses[ids[4]] == "current"
    assert len(audit_rows) == 1
    assert audit_rows[0].metadata_json["dependency_paths"][ids[3]] == ids[:4]


@pytest.mark.asyncio
async def test_world_model_hash_change_automatically_stales_prior_artifacts(api, db):
    headers, project, version_id, world, actor_id = await _workspace(api, "world")
    ids = await _seed_graph(db, project=project, version_id=version_id, world=world, actor_id=actor_id)

    response = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/brief",
        headers=headers,
        json={
            "text": "Six-floor commercial retail building in Riyadh with 18,000 m2 GFA on a 3,000 m2 site and basement parking.",
            "expected_revision": 1,
        },
    )
    assert response.status_code == 201, response.text

    async with db() as session:
        statuses = {
            row.id: row.status for row in (
                await session.scalars(select(ArtifactVersion).where(ArtifactVersion.id.in_(ids)))
            ).all()
        }
        events = list((await session.scalars(
            select(AuditEvent).where(
                AuditEvent.project_id == project["id"],
                AuditEvent.action == "WORLD_MODEL_CHANGE_PROPAGATED",
            )
        )).all())
    assert all(statuses[artifact_id] == "stale" for artifact_id in ids)
    assert len(events) == 1
    assert events[0].metadata_json["changed_artifact_ids"]
    assert events[0].metadata_json["world_model_hash"]


@pytest.mark.asyncio
async def test_propagation_rejects_stale_world_model_hash_without_mutating(api, db):
    headers, project, version_id, world, actor_id = await _workspace(api, "conflict")
    ids = await _seed_graph(db, project=project, version_id=version_id, world=world, actor_id=actor_id)
    response = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/change-impact/propagate",
        headers=headers,
        json={
            "changed_artifact_ids": [ids[0]],
            "expected_world_model_hash": "0" * 64,
            "reason": "Stale page state",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "SOURCE_REVISION_CONFLICT"
    async with db() as session:
        rows = list((await session.scalars(
            select(ArtifactVersion).where(ArtifactVersion.id.in_(ids))
        )).all())
    assert all(row.status == "current" for row in rows)


@pytest.mark.asyncio
async def test_cross_version_dependency_edges_are_reported_but_never_traversed(api, db):
    from app.db.models import ProjectVersion

    headers, project, version_id, world, actor_id = await _workspace(api, "scope")
    ids = await _seed_graph(db, project=project, version_id=version_id, world=world, actor_id=actor_id)
    async with db() as session:
        foreign_version = ProjectVersion(
            id="phase27-other-version",
            organization_id=project["organization_id"],
            project_id=project["id"],
            version=2,
            status="DRAFT",
            revision_number=1,
            change_summary="Isolation test",
            parent_version_id=version_id,
            source="test",
            metadata_json={},
            created_by=actor_id,
        )
        session.add(foreign_version)
        await session.flush()
        session.add(ArtifactVersion(
            id="phase27-foreign-artifact",
            organization_id=project["organization_id"],
            project_id=project["id"],
            project_version_id=foreign_version.id,
            world_model_revision_id=None,
            artifact_type="foreign_version_input",
            version=1,
            status="current",
            provenance_json={"test": "phase27"},
            input_references_json=[],
            output_hash="b" * 64,
            payload_json={},
            created_by=actor_id,
        ))
        await session.flush()
        session.add(ArtifactDependency(
            artifact_version_id=ids[1],
            depends_on_artifact_version_id="phase27-foreign-artifact",
            dependency_kind="input",
        ))
        await session.commit()

    graph_response = await api.get(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/change-impact/graph",
        headers=headers,
    )
    assert graph_response.status_code == 200, graph_response.text
    graph = graph_response.json()
    assert graph["rejected_cross_scope_edge_count"] == 1
    assert graph["integrity"] == "REVIEW_REQUIRED"
    assert all(edge["depends_on_artifact_version_id"] != "phase27-foreign-artifact" for edge in graph["edges"])

    propagated = await api.post(
        f"/api/v1/projects/{project['id']}/versions/{version_id}/change-impact/propagate",
        headers=headers,
        json={
            "changed_artifact_ids": [ids[0]],
            "expected_world_model_hash": world["model_hash"],
            "reason": "Verify version-scoped graph traversal",
        },
    )
    assert propagated.status_code == 200, propagated.text
    async with db() as session:
        foreign = await session.get(ArtifactVersion, "phase27-foreign-artifact")
    assert foreign.status == "current"
