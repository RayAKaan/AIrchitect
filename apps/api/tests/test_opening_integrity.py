import pytest

from app.domains.model.edit_commands import ResizeCommand
from app.domains.model.editing_service import apply_edit
from app.domains.model.schemas import ArchitecturalModel, Building, Door, Level, Point3D, Site, Wall


def model() -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="project-1",
        revision=1,
        site=Site(id="site-1", width_m=20, depth_m=20),
        buildings=(Building(id="building-1", name="Main", site_id="site-1"),),
        levels=(Level(id="level-1", building_id="building-1", name="Ground", elevation_m=0, height_m=3),),
        walls=(Wall(
            id="wall-1", level_id="level-1", name="Wall", start=Point3D(x=0, y=0, z=0),
            end=Point3D(x=5, y=0, z=0), thickness_m=0.2, height_m=3,
        ),),
        doors=(Door(
            id="door-1", level_id="level-1", name="Door", host_wall_id="wall-1",
            offset_m=3, width_m=1.5, height_m=2.1,
        ),),
    )


def test_wall_resize_cannot_orphan_opening() -> None:
    with pytest.raises(ValueError, match="no longer fits"):
        apply_edit(model(), ResizeCommand(element_id="wall-1", scale=0.5))
