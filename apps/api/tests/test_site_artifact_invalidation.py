from types import SimpleNamespace

import pytest

from app.domains.site import service as site_service


@pytest.mark.asyncio
async def test_site_revision_invalidation_targets_all_site_dependent_artifacts(monkeypatch):
    calls = []

    async def fake_invalidate_and_enqueue(
        session,
        *,
        project,
        version,
        source_revision_hash,
        groups,
    ):
        calls.append({
            "session": session,
            "project": project,
            "version": version,
            "source_revision_hash": source_revision_hash,
            "groups": groups,
        })
        return ("artifact-1",)

    monkeypatch.setattr(site_service, "invalidate_and_enqueue", fake_invalidate_and_enqueue)
    session = object()
    project = SimpleNamespace(id="project-1", organization_id="org-1")
    version = SimpleNamespace(id="version-1")
    revision = SimpleNamespace(id="site-revision-2", content_hash="boundary-hash-2")

    invalidated = await site_service.invalidate_site_artifacts(session, project, version, revision)

    assert invalidated == ("artifact-1",)
    assert calls[0]["session"] is session
    assert calls[0]["project"] is project
    assert calls[0]["version"] is version
    assert calls[0]["source_revision_hash"] == site_service._hash_payload({
        "site_revision_id": "site-revision-2",
        "site_revision_hash": "boundary-hash-2",
    })
    assert calls[0]["groups"] == [
        "planning_envelope",
        "design_alternatives",
        "parametric_geometry_intents",
        "quantities",
        "cost",
        "structural_review",
        "validation",
    ]
