from __future__ import annotations

from .edit_commands import EditCommand, ResizeCommand, RotateCommand, TranslateCommand
from .editing import ResizeElement, RotateElement, rotate_element, resize_element
from .schemas import ArchitecturalModel
from .transform import TranslateElement, translate_element


def apply_edit(model: ArchitecturalModel, command: EditCommand) -> ArchitecturalModel:
    """Apply one validated architectural edit and return a new canonical revision."""
    if isinstance(command, TranslateCommand):
        return translate_element(model, TranslateElement(command.element_id, command.dx_m, command.dy_m, command.dz_m))
    if isinstance(command, RotateCommand):
        return rotate_element(model, RotateElement(command.element_id, command.angle_deg))
    if isinstance(command, ResizeCommand):
        return resize_element(model, ResizeElement(command.element_id, command.scale))
    raise TypeError(f"unsupported edit command: {type(command).__name__}")
