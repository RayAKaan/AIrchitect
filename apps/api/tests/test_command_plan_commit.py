from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.domains.commands import routes as command_routes
from app.domains.commands.schemas import CommandEnvelope, CommandResult


def _command() -> CommandEnvelope:
    return CommandEnvelope(
        command_id="move-1",
        type="MoveBuilding",
        schema_version=1,
        project_id="project-1",
        version_id="version-1",
        base_revision_hash="base-hash",
        idempotency_key="move-command-key-1",
        mode="commit",
        reason="move building",
        payload={"element_id": "building-1", "translation_m": {"x": 1, "y": 0, "z": 0}},
    )


@pytest.mark.asyncio
async def test_plan_commit_persists_one_revision_and_uses_reviewed_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _command()
    preview = command_routes.preview_sequential_plan("plan-1", [command])
    assert preview.executable is True
    assert preview.fingerprint is not None
    body = command_routes.PlanCommitRequest(
        plan_id="plan-1", fingerprint=preview.fingerprint, commands=[command]
    )
    project = SimpleNamespace(id="project-1", organization_id="org-1")
    version = SimpleNamespace(id="version-1", revision_number=3)
    source_world = SimpleNamespace(model_hash="base-hash")
    persisted_world = SimpleNamespace(model_hash="persisted-hash")
    model: dict[str, Any] = {}
    state: dict[str, Any] = {"history": []}
    observed: dict[str, Any] = {}

    async def load_model(*args: Any, **kwargs: Any):
        return project, version, source_world, model, state

    async def check_revision(*args: Any, **kwargs: Any) -> None:
        return None

    def execute(plan_model: dict[str, Any], plan_state: dict[str, Any], plan: Any, commands: Any, actor_id: str, revision_hash: str):
        observed["plan_id"] = plan.plan_id
        observed["revision_hash"] = revision_hash
        return SimpleNamespace(
            results=(CommandResult(
                command_id="move-1",
                command_type="MoveBuilding",
                status="committed",
                revision_hash=revision_hash,
                canonical_mutation=True,
            ),),
            model={"semantic_model": {}},
            state={"history": [{"result": {"event_id": "event-1"}}]},
        )

    async def persist(*args: Any, **kwargs: Any):
        observed["persist_commit"] = kwargs["commit"]
        observed["action"] = kwargs["action"]
        observed["designer_state"] = kwargs["model"]["designer_state"]
        return persisted_world

    class InvalidationService:
        async def invalidate_groups(self, session: Any, **kwargs: Any) -> tuple[str, ...]:
            observed["source_revision_hash"] = kwargs["source_revision_hash"]
            observed["groups"] = tuple(kwargs["groups"])
            return ()

    class FakeSession:
        async def commit(self) -> None:
            observed["committed"] = True

    monkeypatch.setattr(command_routes, "load_editable_model", load_model)
    monkeypatch.setattr(command_routes, "check_expected_revision", check_revision)
    monkeypatch.setattr(command_routes, "execute_plan", execute)
    monkeypatch.setattr(command_routes, "persist_designer_mutation", persist)
    monkeypatch.setattr(command_routes, "ArtifactInvalidationService", InvalidationService)

    result = await command_routes.commit_plan(body, SimpleNamespace(id="user-1"), FakeSession())

    assert observed["plan_id"] == "plan-1"
    assert observed["revision_hash"] == "base-hash"
    assert observed["persist_commit"] is False
    assert observed["action"] == "COMMAND_PLAN"
    assert observed["designer_state"]["history"][0]["result"]["event_id"] == "event-1"
    assert observed["source_revision_hash"] == "persisted-hash"
    assert observed["committed"] is True
    assert result.status == "committed"
    assert result.revision_hash == "persisted-hash"


@pytest.mark.asyncio
async def test_plan_commit_rejects_changed_fingerprint_before_loading_project(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _command()
    body = command_routes.PlanCommitRequest(
        plan_id="plan-1", fingerprint="0" * 64, commands=[command]
    )
    loaded = False

    async def load_model(*args: Any, **kwargs: Any):
        nonlocal loaded
        loaded = True
        raise AssertionError("project must not load for a mismatched plan fingerprint")

    monkeypatch.setattr(command_routes, "load_editable_model", load_model)

    with pytest.raises(ValueError, match="PLAN_FINGERPRINT_MISMATCH"):
        await command_routes.commit_plan(body, SimpleNamespace(id="user-1"), SimpleNamespace())
    assert loaded is False
