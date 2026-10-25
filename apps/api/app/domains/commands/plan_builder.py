from __future__ import annotations

from collections.abc import Sequence
from .plan import CommandPlan, PlanNode
from .schemas import CommandEnvelope


def build_sequential_plan(plan_id: str, commands: Sequence[CommandEnvelope]) -> CommandPlan:
    if not commands:
        raise ValueError("command plan must contain at least one command")
    first = commands[0]
    nodes = tuple(
        PlanNode(
            node_id=command.command_id,
            command_id=command.command_id,
            depends_on=(commands[index - 1].command_id,) if index else (),
        )
        for index, command in enumerate(commands)
    )
    plan = CommandPlan(plan_id, first.project_id, first.version_id, first.base_revision_hash, nodes)
    plan.validate()
    if any(command.project_id != first.project_id or command.version_id != first.version_id for command in commands):
        raise ValueError("all commands in a plan must target the same project and version")
    if any(command.base_revision_hash != first.base_revision_hash for command in commands):
        raise ValueError("all commands in a plan must share the same base revision")
    return plan
