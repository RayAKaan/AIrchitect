import pytest

from app.domains.geometry.model_derivation import derive_model_meshes
from app.domains.model import ArchitecturalModel, Building, Door, Level, Point3D, Site, Wall


def make_model(*, doors: tuple[Door, ...] = ()) -> ArchitecturalModel:
    site = Site(id="site", width_m=20, depth_m=20)
    building = Building(id="building", name="Building", site_id=site.id)
    level = Level(id="level", building_id=building.id, name="Ground", elevation_m=0, height_m=3)
    wall = Wall(
        id="wall",
        name="Wall",
        level_id=level.id,
        start=Point3D(x=0, y=0, z=0),
        end=Point3D(x=6, y=0, z=0),
        thickness_m=0.2,
        height_m=3,
    )
    return ArchitecturalModel(
        project_id="project",
        revision=1,
        site=site,
        buildings=(building,),
        levels=(level,),
        walls=(wall,),
        doors=doors,
    )


def test_door_creates_a_real_void_in_wall_mesh() -> None:
    door = Door(
        id="door",
        name="Entry",
        level_id="level",
        host_wall_id="wall",
        offset_m=2,
        width_m=1,
        height_m=2.1,
    )
    mesh = derive_model_meshes(make_model(doors=(door,)))[0]
    assert mesh.element_id == "wall"
    assert len(mesh.faces) > 6
    assert max(vertex[2] for vertex in mesh.vertices) == 3


def test_overlapping_openings_fail_closed() -> None:
    doors = (
        Door(id="door-a", name="A", level_id="level", host_wall_id="wall", offset_m=1, width_m=2, height_m=2),
        Door(id="door-b", name="B", level_id="level", host_wall_id="wall", offset_m=2, width_m=2, height_m=2),
    )
    with pytest.raises(ValueError, match="overlap"):
        derive_model_meshes(make_model(doors=doors))
