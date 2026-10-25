from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Sequence

from .executor import execute_semantic_command
from .schemas import CommandEnvelope, CommandResult


@dataclass(frozen=True)
class BatchExecution:
    results: tuple[CommandResult, ...]
    model: dict[str, Any]
    state: dict[str, Any]


def execute_command_batch(model: dict[str, Any], state: dict[str, Any], commands: Sequence[CommandEnvelope], actor_id: str, revision_hash: str) -> BatchExecution:
    """Execute a command sequence atomically in memory; caller persists once."""
    if not commands:
        raise ValueError("command batch must not be empty")
    working_model = copy.deepcopy(model)
    working_state = copy.deepcopy(state)
    results: list[CommandResult] = []
    try:
        for command in commands:
            results.append(execute_semantic_command(working_model, working_state, command, actor_id, revision_hash))
    except Exception:
        raise
    return BatchExecution(tuple(results), working_model, working_state)
