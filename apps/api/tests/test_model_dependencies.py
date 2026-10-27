from app.domains.model import ArchitecturalModel, Building, Level, Point3D, Site, Space, Wall
from app.domains.model.dependencies import build_model_dependency_graph


def make_model() -> ArchitecturalModel:
    site = Site(id="site", width_m=20, depth_m=20)
    building = Building(id="building", name="Building", site_id=site.id)
    level = Level(id="level", building_id=building.id, name="Ground", elevation_m=0, height_m=3)
    space = Space(
        id="space",
        name="Living",
        level_id=level.id,
        boundary=(
            Point3D(x=0, y=0, z=0),
            Point3D(x=4, y=0, z=0),
            Point3D(x=4, y=4, z=0),
        ),
    )
    wall = Wall(
        id="wall",
        name="Wall",
        level_id=level.id,
        start=Point3D(x=0, y=0, z=0),
        end=Point3D(x=4, y=0, z=0),
        thickness_m=0.2,
        height_m=3,
        space_ids=(space.id,),
    )
    return ArchitecturalModel(
        project_id="project",
        revision=1,
        site=site,
        buildings=(building,),
        levels=(level,),
        spaces=(space,),
        walls=(wall,),
    )


def test_graph_contains_direct_references() -> None:
    graph = build_model_dependency_graph(make_model())
    assert graph.direct_dependencies("wall") == ("level", "space")


def test_affected_by_returns_transitive_reverse_closure() -> None:
    graph = build_model_dependency_graph(make_model())
    assert graph.affected_by({"building"}) == ("building", "level", "space", "wall")
