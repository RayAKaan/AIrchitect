from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .batch import BatchExecution, execute_command_batch
from .batch_contract import validate_command_batch
from .plan import CommandPlan
from .schemas import CommandEnvelope


def execute_plan(
    model: dict[str, Any],
    state: dict[str, Any],
    plan: CommandPlan,
    commands: Sequence[CommandEnvelope],
    actor_id: str,
    revision_hash: str,
) -> BatchExecution:
    plan.validate()
    validate_command_batch(commands)
    if plan.project_id != commands[0].project_id or plan.version_id != commands[0].version_id:
        raise ValueError("plan and command context do not match")
    if plan.base_revision_hash != commands[0].base_revision_hash:
        raise ValueError("plan and command revision do not match")
    if plan.base_revision_hash != revision_hash:
        raise ValueError("execution revision does not match plan base revision")

    by_id = {command.command_id: command for command in commands}
    plan_command_ids = {node.command_id for node in plan.nodes}
    if set(by_id) != plan_command_ids:
        raise ValueError("plan and command set do not match")

    command_by_node = {node.node_id: by_id[node.command_id] for node in plan.nodes}
    ordered = [command_by_node[node_id] for node_id in plan.execution_order()]
    return execute_command_batch(model, state, ordered, actor_id, revision_hash)
