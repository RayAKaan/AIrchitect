from __future__ import annotations

import pytest

from app.domains.drawings.engine import build_drawing_package
from app.domains.model import (
    ArchitecturalModel, Building, Door, Level, Point3D, Site, Slab, Space, Wall,
)


def _model() -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="project-1",
        revision=7,
        site=Site(id="site-1", width_m=20, depth_m=20),
        buildings=(Building(id="building-1", name="Main", site_id="site-1"),),
        levels=(Level(id="level-1", building_id="building-1", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(
            id="room-1", level_id="level-1", name="Room",
            boundary=(
                Point3D(x=0, y=0, z=0), Point3D(x=8, y=0, z=0),
                Point3D(x=8, y=6, z=0), Point3D(x=0, y=6, z=0),
            ),
        ),),
        walls=(Wall(
            id="wall-1", level_id="level-1", name="South wall",
            start=Point3D(x=0, y=0, z=0), end=Point3D(x=8, y=0, z=0),
            thickness_m=0.2, height_m=3,
        ),),
        doors=(Door(
            id="door-1", level_id="level-1", name="Entry", host_wall_id="wall-1",
            offset_m=1, width_m=0.9, height_m=2.1,
        ),),
        slabs=(Slab(
            id="slab-1", level_id="level-1", name="Ground slab",
            boundary=(
                Point3D(x=0, y=0, z=0), Point3D(x=8, y=0, z=0),
                Point3D(x=8, y=6, z=0), Point3D(x=0, y=6, z=0),
            ), thickness_m=0.25,
        ),),
    )


def test_drawing_package_derives_stable_plan_and_elevation_from_canonical_model():
    model = _model()
    first = build_drawing_package(model)
    second = build_drawing_package(model)

    assert first == second
    assert first["source_model_hash"]
    assert first["drawing_hash"]
    assert first["units"] == "m"
    assert first["coordinate_system"] == "local_cartesian_z_up"
    assert [view["id"] for view in first["views"]] == ["plan"]
    plan = first["views"][0]["primitives"]
    assert {item["element_id"] for item in plan} == {"room-1", "slab-1", "wall-1", "door-1"}
    door_line = next(item for item in plan if item["element_id"] == "door-1")
    assert door_line["start"] == {"x": 1.0, "y": 0.0}
    assert door_line["end"] == {"x": 1.9, "y": 0.0}
    wall_elevation = next(item for item in first["elevations"][0]["primitives"] if item["element_id"] == "wall-1")
    assert wall_elevation["start"] == {"x": 0.0, "y": 0.0}
    assert wall_elevation["end"] == {"x": 8.0, "y": 3.0}
    opening_elevation = next(item for item in first["elevations"][0]["primitives"] if item["element_id"] == "door-1")
    assert opening_elevation["start"] == {"x": 1.0, "y": 0.0}
    assert opening_elevation["end"] == {"x": 1.9, "y": 2.1}


def test_drawing_package_fails_closed_when_opening_exceeds_host_wall():
    model = _model()
    invalid_door = model.doors[0].model_copy(update={"offset_m": 7.5})
    invalid = model.model_copy(update={"doors": (invalid_door,)})
    with pytest.raises(ValueError, match="DRAWING_OPENING_OUTSIDE_HOST"):
        build_drawing_package(invalid)


def test_drawing_generation_and_retrieval_routes_are_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/projects/{project_id}/drawings/generate" in paths
    assert "/api/v1/projects/{project_id}/drawings" in paths
