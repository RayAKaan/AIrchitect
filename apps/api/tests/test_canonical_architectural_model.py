import pytest
from pydantic import ValidationError

from app.domains.model.identity import model_hash
from app.domains.model.schemas import (
    ArchitecturalModel,
    Building,
    Level,
    Point3D,
    Site,
    Space,
    Wall,
)


def make_model() -> ArchitecturalModel:
    site = Site(id="site-1", width_m=20, depth_m=30)
    building = Building(id="building-1", name="Main Building", site_id=site.id)
    level = Level(id="level-1", building_id=building.id, name="Ground", elevation_m=0, height_m=3)
    space = Space(
        id="space-1",
        name="Living",
        level_id=level.id,
        boundary=(
            Point3D(x=0, y=0, z=0),
            Point3D(x=5, y=0, z=0),
            Point3D(x=5, y=4, z=0),
            Point3D(x=0, y=4, z=0),
        ),
    )
    wall = Wall(
        id="wall-1",
        name="North Wall",
        level_id=level.id,
        start=Point3D(x=0, y=4, z=0),
        end=Point3D(x=5, y=4, z=0),
        thickness_m=0.2,
        height_m=3,
        space_ids=(space.id,),
    )
    return ArchitecturalModel(
        project_id="project-1",
        revision=1,
        site=site,
        buildings=(building,),
        levels=(level,),
        spaces=(space,),
        walls=(wall,),
    )


def test_valid_model_is_hashable_and_stable() -> None:
    model = make_model()
    assert len(model_hash(model)) == 64
    assert model_hash(model) == model_hash(model.model_copy(deep=True))


def test_duplicate_ids_are_rejected() -> None:
    model = make_model()
    with pytest.raises(ValidationError, match="globally unique"):
        ArchitecturalModel(
            project_id=model.project_id,
            revision=2,
            site=model.site,
            buildings=model.buildings,
            levels=model.levels,
            spaces=model.spaces,
            walls=(model.walls[0].model_copy(update={"id": "space-1"}),),
        )


def test_unknown_level_reference_is_rejected() -> None:
    model = make_model()
    with pytest.raises(ValidationError, match="unknown level"):
        ArchitecturalModel(
            project_id=model.project_id,
            revision=2,
            site=model.site,
            buildings=model.buildings,
            levels=model.levels,
            spaces=model.spaces,
            walls=(model.walls[0].model_copy(update={"level_id": "missing"}),),
        )


def test_opening_requires_existing_wall() -> None:
    from app.domains.model.schemas import Door

    with pytest.raises(ValidationError, match="unknown wall"):
        ArchitecturalModel(
            project_id="project-1",
            revision=1,
            site=Site(id="site-1", width_m=20, depth_m=30),
            doors=(
                Door(
                    id="door-1",
                    name="Entry",
                    level_id="level-1",
                    host_wall_id="missing-wall",
                    offset_m=0,
                    width_m=0.9,
                    height_m=2.1,
                ),
            ),
        )
