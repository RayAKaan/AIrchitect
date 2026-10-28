from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.domains.commands import routes as command_routes
from app.domains.commands.schemas import CommandEnvelope, CommandResult


@pytest.mark.asyncio
async def test_command_regeneration_uses_persisted_hash_in_same_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, Any] = {}
    project = SimpleNamespace(id="project-1", organization_id="org-1")
    version = SimpleNamespace(id="version-1", revision_number=4)
    source_world = SimpleNamespace(model_hash="base-hash")
    persisted_world = SimpleNamespace(model_hash="persisted-canonical-hash")
    model: dict[str, Any] = {}
    state: dict[str, Any] = {"history": []}
    commits: list[bool] = []

    async def load_model(*args: Any, **kwargs: Any):
        return project, version, source_world, model, state

    async def check_revision(*args: Any, **kwargs: Any) -> None:
        return None

    def execute(*args: Any, **kwargs: Any) -> CommandResult:
        return CommandResult(
            command_id="command-1",
            command_type="MoveBuilding",
            status="committed",
            revision_hash="base-hash",
            canonical_mutation=True,
        )

    async def persist(*args: Any, **kwargs: Any):
        observed["commit_flag"] = kwargs["commit"]
        return persisted_world

    class InvalidationService:
        async def invalidate_groups(self, session: Any, **kwargs: Any) -> tuple[str, ...]:
            observed["source_revision_hash"] = kwargs["source_revision_hash"]
            return ()

    async def commit_session() -> None:
        commits.append(True)

    monkeypatch.setattr(command_routes, "load_editable_model", load_model)
    monkeypatch.setattr(command_routes, "check_expected_revision", check_revision)
    monkeypatch.setattr(command_routes, "execute_semantic_command", execute)
    monkeypatch.setattr(command_routes, "persist_designer_mutation", persist)
    monkeypatch.setattr(command_routes, "ArtifactInvalidationService", InvalidationService)

    body = CommandEnvelope(
        command_id="command-1",
        type="MoveBuilding",
        schema_version=1,
        project_id="project-1",
        version_id="version-1",
        base_revision_hash="base-hash",
        idempotency_key="command-idempotency-1",
        mode="commit",
        reason="move building",
        payload={"element_id": "building-1", "translation_m": {"x": 1, "y": 0, "z": 0}},
    )
    user = SimpleNamespace(id="user-1")
    session = SimpleNamespace(commit=commit_session)

    result = await command_routes.commit(body, user, session)

    assert observed["commit_flag"] is False
    assert observed["source_revision_hash"] == persisted_world.model_hash
    assert result.revision_hash == persisted_world.model_hash
    assert commits == [True]
