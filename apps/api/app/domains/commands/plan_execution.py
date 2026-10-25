from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from .batch import BatchExecution, execute_command_batch
from .batch_contract import validate_command_batch
from .plan import CommandPlan
from .schemas import CommandEnvelope


def execute_plan(model: dict[str, Any], state: dict[str, Any], plan: CommandPlan, commands: Sequence[CommandEnvelope], actor_id: str, revision_hash: str) -> BatchExecution:
    plan.validate()
    validate_command_batch(commands)
    by_id = {command.command_id: command for command in commands}
    if set(by_id) != {node.command_id for node in plan.nodes}:
        raise ValueError("plan and command set do not match")
    ordered = [by_id[node_id] for node_id in plan.execution_order()]
    return execute_command_batch(model, state, ordered, actor_id, revision_hash)
