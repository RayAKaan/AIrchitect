from __future__ import annotations

from collections.abc import Sequence
from .schemas import CommandEnvelope


def validate_command_batch(commands: Sequence[CommandEnvelope]) -> None:
    if not commands:
        raise ValueError("command batch must not be empty")
    first = commands[0]
    ids = [command.command_id for command in commands]
    if len(ids) != len(set(ids)):
        raise ValueError("command ids must be unique within a batch")
    if any(command.project_id != first.project_id or command.version_id != first.version_id for command in commands):
        raise ValueError("all commands in a batch must target the same project and version")
    if any(command.base_revision_hash != first.base_revision_hash for command in commands):
        raise ValueError("all commands in a batch must share the same base revision")
    if any(command.mode != first.mode for command in commands):
        raise ValueError("all commands in a batch must use the same execution mode")
