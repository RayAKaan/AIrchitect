from __future__ import annotations

from collections.abc import Sequence

from .edit_commands import EditCommand
from .editing_service import apply_edit
from .schemas import ArchitecturalModel


def apply_edit_batch(model: ArchitecturalModel, commands: Sequence[EditCommand]) -> ArchitecturalModel:
    """Apply an ordered edit batch atomically as one canonical revision."""
    if not commands:
        raise ValueError("at least one edit command is required")
    current = model
    for command in commands:
        current = apply_edit(current, command)
    return current.model_copy(update={"revision": model.revision + 1})
