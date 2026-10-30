from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domains.requirements import persistence


@pytest.mark.parametrize("target_status", ["CONFIRMED", "REJECTED"])
async def test_requirement_decision_invalidates_program_and_downstream_artifacts(monkeypatch, target_status):
    project = SimpleNamespace(id="project-1", organization_id="org-1")
    version = SimpleNamespace(id="version-1", revision_number=7)
    user = SimpleNamespace(id="user-1")
    requirement = SimpleNamespace(
        id="requirement-1",
        parameter="target_gfa",
        category="spatial",
        normalized_value_json=1200,
        unit="m2",
        source_text="1200 square metres",
        source_type="USER_BRIEF",
        extraction_method="deterministic_pattern_v2",
        confidence=0.95,
        status="EXTRACTED",
        contradiction_group=None,
        provenance_json={"brief_hash": "brief-hash"},
        confirmed_at=None,
        confirmed_by=None,
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=requirement),
        commit=AsyncMock(),
    )
    audit = AsyncMock()
    persist_world_model = AsyncMock(return_value=SimpleNamespace(id="world-2", model_hash="world-hash-2"))
    invalidate = AsyncMock()
    monkeypatch.setattr(persistence, "resolve_project_version", AsyncMock(return_value=(project, version)))
    monkeypatch.setattr(persistence, "audit", audit)
    monkeypatch.setattr(persistence, "persist_world_model", persist_world_model)
    monkeypatch.setattr(persistence, "invalidate_and_enqueue", invalidate)

    result = await persistence.set_status(
        session,
        project.id,
        "version-1",
        requirement.id,
        target_status,
        user,
        expected_revision=7,
    )

    assert result["world_model_hash"] == "world-hash-2"
    assert version.revision_number == 8
    assert requirement.status == target_status
    invalidate.assert_awaited_once()
    kwargs = invalidate.await_args.kwargs
    assert kwargs["project"] is project
    assert kwargs["version"] is version
    assert kwargs["source_revision_hash"] == "world-hash-2"
    assert kwargs["groups"] == (
        "program",
        "design_alternatives",
        "parametric_geometry_intents",
        "quantities",
        "cost",
        "structural_review",
        "validation",
    )
    session.commit.assert_awaited_once()
