import pytest

from app.domains.model.edit_commands import ResizeCommand, RotateCommand, TranslateCommand
from app.domains.model.editing_service import apply_edit
from app.domains.model.schemas import ArchitecturalModel, Point3D, Site, Space


def model() -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="project-1",
        revision=1,
        site=Site(id="site-1", width_m=20, depth_m=20),
        spaces=(Space(
            id="space-1",
            level_id="level-1",
            name="Room",
            boundary=(Point3D(x=0, y=0, z=0), Point3D(x=4, y=0, z=0), Point3D(x=4, y=3, z=0)),
        ),),
    )


def test_translate_rotate_resize_each_create_new_revision() -> None:
    source = model()
    translated = apply_edit(source, TranslateCommand(element_id="space-1", dx_m=2, dy_m=1, dz_m=0))
    rotated = apply_edit(translated, RotateCommand(element_id="space-1", angle_deg=90))
    resized = apply_edit(rotated, ResizeCommand(element_id="space-1", scale=0.5))

    assert source.revision == 1
    assert translated.revision == 2
    assert rotated.revision == 3
    assert resized.revision == 4
    assert translated is not source
    assert rotated is not translated
    assert resized is not rotated


def test_resize_rejects_non_positive_scale() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        apply_edit(model(), ResizeCommand(element_id="space-1", scale=0.0))
