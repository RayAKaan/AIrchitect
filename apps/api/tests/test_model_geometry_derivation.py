from app.domains.geometry.model_derivation import derive_model_meshes
from app.domains.model import ArchitecturalModel, Building, Level, Point3D, Site, Wall


def make_model() -> ArchitecturalModel:
    site = Site(id="site", width_m=20, depth_m=20)
    building = Building(id="building", name="Building", site_id=site.id)
    level = Level(id="level", building_id=building.id, name="Ground", elevation_m=0, height_m=3)
    wall = Wall(
        id="wall",
        name="Wall",
        level_id=level.id,
        start=Point3D(x=0, y=0, z=0),
        end=Point3D(x=5, y=0, z=0),
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
    )


def test_wall_mesh_is_parametric_and_deterministic() -> None:
    model = make_model()
    first = derive_model_meshes(model)
    second = derive_model_meshes(model)
    assert first == second
    assert len(first) == 1
    assert first[0].element_id == "wall"
    assert len(first[0].vertices) == 8
    assert len(first[0].faces) == 6
    assert first[0].source_model_hash
    assert len(first[0].geometry_hash) == 64
