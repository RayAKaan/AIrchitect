from app.domains.model.constraints import validate_baseline_constraints
from app.domains.model.schemas import ArchitecturalModel, Building, Door, Level, Point3D, Site, Wall


def test_opening_outside_wall_is_reported() -> None:
    site = Site(id="site", width_m=20, depth_m=20)
    building = Building(id="building", name="Building", site_id=site.id)
    level = Level(id="level", building_id=building.id, name="Ground", elevation_m=0, height_m=3)
    wall = Wall(
        id="wall",
        name="Wall",
        level_id=level.id,
        start=Point3D(x=0, y=0, z=0),
        end=Point3D(x=4, y=0, z=0),
        thickness_m=0.2,
        height_m=3,
    )
    door = Door(
        id="door",
        name="Door",
        level_id=level.id,
        host_wall_id=wall.id,
        offset_m=3.5,
        width_m=1,
        height_m=2,
    )
    model = ArchitecturalModel(
        project_id="project",
        revision=1,
        site=site,
        buildings=(building,),
        levels=(level,),
        walls=(wall,),
        doors=(door,),
    )
    violations = validate_baseline_constraints(model)
    assert [item.code for item in violations] == ["opening_outside_wall"]


def test_valid_opening_has_no_baseline_violations() -> None:
    site = Site(id="site", width_m=20, depth_m=20)
    building = Building(id="building", name="Building", site_id=site.id)
    level = Level(id="level", building_id=building.id, name="Ground", elevation_m=0, height_m=3)
    wall = Wall(
        id="wall",
        name="Wall",
        level_id=level.id,
        start=Point3D(x=0, y=0, z=0),
        end=Point3D(x=4, y=0, z=0),
        thickness_m=0.2,
        height_m=3,
    )
    door = Door(
        id="door",
        name="Door",
        level_id=level.id,
        host_wall_id=wall.id,
        offset_m=1,
        width_m=1,
        height_m=2,
    )
    model = ArchitecturalModel(
        project_id="project",
        revision=1,
        site=site,
        buildings=(building,),
        levels=(level,),
        walls=(wall,),
        doors=(door,),
    )
    assert validate_baseline_constraints(model) == ()
