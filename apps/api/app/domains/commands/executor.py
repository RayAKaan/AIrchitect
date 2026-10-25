from __future__ import annotations

from typing import Any

from .contract import canonical_payload
from .idempotency import find_replay, record_command
from .impact import impact_for
from .preconditions import check_preconditions
from .schemas import CommandEnvelope, CommandResult
from .semantic_adapter import apply_semantic_command
from .service import validate_command


def execute_semantic_command(model: dict[str, Any], state: dict[str, Any], command: CommandEnvelope, actor_id: str, revision_hash: str) -> CommandResult:
    if command.mode != "commit":
        raise ValueError("command executor only accepts commit mode")
    validation = validate_command(command)
    if not validation.valid:
        raise ValueError("; ".join(validation.errors))
    replay = find_replay(state, command)
    if replay is not None:
        result = replay["result"]
        return CommandResult(**{**result, "status": "replayed", "canonical_mutation": False})
    # Rebuild the envelope from canonical payload so execution cannot diverge
    # from preview/validation normalization.
    canonical = command.model_copy(update={"payload": canonical_payload(command)})
    errors = check_preconditions(model, state, canonical)
    if errors:
        raise ValueError("; ".join(errors))
    event = apply_semantic_command(model, state, canonical, actor_id)
    result = CommandResult(
        command_id=command.command_id,
        command_type=command.type,
        status="committed",
        revision_hash=revision_hash,
        canonical_mutation=True,
        impact=impact_for(command),
        warnings=[],
    )
    record_command(state, canonical, {**result.model_dump(), "event": event})
    return result
