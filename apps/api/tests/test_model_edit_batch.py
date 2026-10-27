from app.domains.model.edit_batch import apply_edit_batch
from app.domains.model.edit_commands import ResizeCommand, TranslateCommand
from app.domains.model.schemas import ArchitecturalModel, Building, Level, Point3D, Site, Space


def model() -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="project-1",
        revision=4,
        site=Site(id="site-1", width_m=20, depth_m=20),
        buildings=(Building(id="building-1", name="Main", site_id="site-1"),),
        levels=(Level(id="level-1", building_id="building-1", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(
            id="space-1", level_id="level-1", name="Room",
            boundary=(Point3D(x=0, y=0, z=0), Point3D(x=4, y=0, z=0), Point3D(x=4, y=3, z=0)),
        ),),
    )


def test_batch_is_exposed_as_one_revision() -> None:
    result = apply_edit_batch(model(), (
        TranslateCommand(element_id="space-1", dx_m=2, dy_m=0, dz_m=0),
        ResizeCommand(element_id="space-1", scale=0.5),
    ))
    assert result.revision == 5
    assert result.spaces[0].boundary != model().spaces[0].boundary
