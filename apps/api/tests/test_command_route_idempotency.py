from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.domains.commands import routes as command_routes
from app.domains.commands.idempotency import record_command
from app.domains.commands.schemas import CommandEnvelope


def _command(command_id: str, *, element_id: str = "space-1", revision: str = "old-hash") -> CommandEnvelope:
    return CommandEnvelope(
        command_id=command_id,
        type="ResizeSpace",
        schema_version=1,
        project_id="project-1",
        version_id="version-1",
        base_revision_hash=revision,
        idempotency_key=f"idempotency-{command_id}-key",
        mode="commit",
        reason="resize reviewed space",
        payload={"element_id": element_id, "area_m2": 20.0},
    )


def _record(state: dict[str, Any], command: CommandEnvelope) -> None:
    record_command(state, command, {
        "command_id": command.command_id,
        "command_type": command.type,
        "status": "committed",
        "revision_hash": command.base_revision_hash,
        "canonical_mutation": True,
        "impact": ["quantities"],
        "warnings": [],
    })


def _project_context(state: dict[str, Any]):
    project = SimpleNamespace(id="project-1", organization_id="org-1")
    version = SimpleNamespace(id="version-1", revision_number=8)
    world = SimpleNamespace(model_hash="new-current-hash")
    model: dict[str, Any] = {}

    async def load_model(*args: Any, **kwargs: Any):
        return project, version, world, model, state

    async def check_revision(*args: Any, **kwargs: Any) -> None:
        return None

    return load_model, check_revision


@pytest.mark.asyncio
async def test_single_command_retry_replays_even_when_base_revision_is_now_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _command("command-1")
    state: dict[str, Any] = {"history": []}
    _record(state, command)
    load_model, check_revision = _project_context(state)
    monkeypatch.setattr(command_routes, "load_editable_model", load_model)
    monkeypatch.setattr(command_routes, "check_expected_revision", check_revision)

    result = await command_routes.commit(command, SimpleNamespace(id="user-1"), SimpleNamespace())

    assert result.status == "replayed"
    assert result.canonical_mutation is False
    assert result.revision_hash == "new-current-hash"


@pytest.mark.asyncio
async def test_plan_retry_replays_all_commands_before_stale_base_check(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = [_command("command-1"), _command("command-2", element_id="space-2")]
    state: dict[str, Any] = {"history": []}
    for command in commands:
        _record(state, command)
    preview = command_routes.preview_sequential_plan("plan-1", commands)
    assert preview.executable is True and preview.fingerprint is not None
    body = command_routes.PlanCommitRequest(
        plan_id="plan-1", fingerprint=preview.fingerprint, commands=commands
    )
    load_model, check_revision = _project_context(state)
    monkeypatch.setattr(command_routes, "load_editable_model", load_model)
    monkeypatch.setattr(command_routes, "check_expected_revision", check_revision)
    monkeypatch.setattr(command_routes, "execute_plan", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("replay must not execute")))

    result = await command_routes.commit_plan(body, SimpleNamespace(id="user-1"), SimpleNamespace())

    assert result.status == "replayed"
    assert result.revision_hash == "new-current-hash"
    assert [item.status for item in result.command_results] == ["replayed", "replayed"]
    assert result.invalidated_artifact_ids == []


@pytest.mark.asyncio
async def test_plan_retry_rejects_partial_replay_without_mutating(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = [_command("command-1"), _command("command-2", element_id="space-2")]
    state: dict[str, Any] = {"history": []}
    _record(state, commands[0])
    load_model, check_revision = _project_context(state)
    monkeypatch.setattr(command_routes, "load_editable_model", load_model)
    monkeypatch.setattr(command_routes, "check_expected_revision", check_revision)

    preview = command_routes.preview_sequential_plan("plan-1", commands)
    assert preview.fingerprint is not None
    body = command_routes.PlanCommitRequest(
        plan_id="plan-1", fingerprint=preview.fingerprint, commands=commands
    )
    with pytest.raises(ValueError, match="PARTIAL_PLAN_REPLAY"):
        await command_routes.commit_plan(body, SimpleNamespace(id="user-1"), SimpleNamespace())
