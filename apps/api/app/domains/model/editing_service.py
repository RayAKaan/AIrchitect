from __future__ import annotations

from .edit_commands import EditCommand, ResizeCommand, RotateCommand, TranslateCommand
from .editing import ResizeElement, RotateElement, rotate_element, resize_element
from .opening_integrity import validate_opening_integrity
from .schemas import ArchitecturalModel
from .transform import TranslateElement, translate_element


def apply_edit(model: ArchitecturalModel, command: EditCommand) -> ArchitecturalModel:
    """Apply one validated architectural edit and return a new canonical revision."""
    if isinstance(command, TranslateCommand):
        result = translate_element(model, TranslateElement(command.element_id, command.dx_m, command.dy_m, command.dz_m))
    elif isinstance(command, RotateCommand):
        result = rotate_element(model, RotateElement(command.element_id, command.angle_deg))
    elif isinstance(command, ResizeCommand):
        result = resize_element(model, ResizeElement(command.element_id, command.scale))
    else:
        raise TypeError(f"unsupported edit command: {type(command).__name__}")
    validate_opening_integrity(result)
    return result
