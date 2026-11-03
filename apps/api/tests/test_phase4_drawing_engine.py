from __future__ import annotations

import pytest

from app.domains.drawings.engine import build_drawing_package
from app.domains.drawings.documentation import build_drawing_documentation
from app.domains.drawings.site_circulation import build_site_circulation_package
from app.domains.drawings.environmental_spatial import analyze_environmental_spatial_performance
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
    assert "/api/v1/projects/{project_id}/drawings/document" in paths


def test_drawing_package_keeps_unassigned_elements_visible_without_storeys():
    model = ArchitecturalModel(
        project_id="project-2", revision=1,
        site=Site(id="site-2", width_m=10, depth_m=10),
        walls=(Wall(
            id="wall-unassigned", name="Unassigned wall",
            start=Point3D(x=0, y=0, z=0), end=Point3D(x=5, y=0, z=0),
            thickness_m=0.2, height_m=3,
        ),),
    )
    package = build_drawing_package(model)
    assert package["views"][0]["id"] == "plan"
    assert package["views"][0]["level_id"] is None
    assert package["views"][0]["primitives"][0]["element_id"] == "wall-unassigned"


def test_drawing_documentation_contains_measured_dimensions_schedules_and_sheet_lineage():
    model = _model()
    drawing = build_drawing_package(model)
    document = build_drawing_documentation(model, drawing)

    assert document["source_model_hash"] == drawing["source_model_hash"]
    assert document["source_drawing_hash"] == drawing["drawing_hash"]
    assert document["documentation_hash"]
    assert {item["property"] for item in document["dimensions"] if item["element_id"] == "wall-1"} == {
        "length", "height", "thickness",
    }
    assert document["schedules"]["spaces"][0]["area_m2"] == 48.0
    assert document["schedules"]["doors"][0]["host_wall_id"] == "wall-1"
    assert document["sheets"][0]["issue_status"] == "REVIEW"
    assert document["sheets"][0]["scale"] is None


def test_drawing_documentation_rejects_stale_drawing_package():
    model = _model()
    drawing = build_drawing_package(model)
    drawing["views"][0]["primitives"].clear()
    with pytest.raises(ValueError, match="DRAWING_PACKAGE_HASH_INVALID"):
        build_drawing_documentation(model, drawing)


def test_site_circulation_package_is_deterministic_and_does_not_claim_unverified_routes():
    model = _model()
    wall = model.walls[0].model_copy(update={"space_ids": ("room-1",)})
    model = model.model_copy(update={"walls": (wall,)})
    first = build_site_circulation_package(model)
    second = build_site_circulation_package(model)

    assert first == second
    assert first["source_model_hash"]
    assert first["package_hash"]
    assert first["site"]["area_m2"] == 400.0
    assert first["building_footprints"][0]["within_site"] is True
    assert first["access_candidates"][0]["id"] == "door-1"
    assert first["access_candidates"][0]["adjacent_space_ids"] == ["room-1"]
    assert first["circulation"]["status"] == "CANDIDATE_GRAPH_ONLY"
    assert first["circulation"]["edges"] == []
    assert first["circulation"]["route_geometry"] == []
    assert first["circulation"]["unknowns"]


def test_site_circulation_package_reports_footprints_outside_canonical_site():
    model = _model()
    slab = model.slabs[0].model_copy(update={
        "boundary": (
            Point3D(x=-1, y=0, z=0), Point3D(x=8, y=0, z=0),
            Point3D(x=8, y=6, z=0), Point3D(x=-1, y=6, z=0),
        ),
    })
    invalid = model.model_copy(update={"slabs": (slab,)})
    package = build_site_circulation_package(invalid)
    assert package["site_constraints"]["footprints_within_site"] is False
    assert package["site_constraints"]["outside_site_area_m2"] == 6.0


def test_site_circulation_api_routes_are_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/projects/{project_id}/site-circulation/generate" in paths
    assert "/api/v1/projects/{project_id}/site-circulation" in paths


def test_environmental_spatial_analysis_derives_auditable_room_metrics():
    model = _model()
    wall = model.walls[0].model_copy(update={"space_ids": ("room-1",)})
    window = model.doors[0].model_copy(update={
        "id": "window-1", "element_type": "window", "width_m": 1.2,
        "height_m": 1.0, "offset_m": 3.0, "sill_height_m": 0.9,
    })
    model = model.model_copy(update={"walls": (wall,), "doors": (), "windows": (window,)})
    result = analyze_environmental_spatial_performance(model)

    assert result["source_model_hash"]
    assert result["analysis_hash"]
    room = result["room_metrics"][0]
    assert room["floor_area_m2"] == 48.0
    assert room["window_opening_area_m2"] == 1.2
    assert room["window_to_floor_area_ratio"] == 0.025
    assert room["daylight_illuminance"]["status"] == "UNKNOWN"
    assert result["environmental"]["daylight"]["status"] == "NOT_SIMULATED"


def test_environmental_spatial_analysis_reports_shared_space_boundary():
    model = _model()
    first = model.spaces[0]
    second = first.model_copy(update={
        "id": "room-2", "name": "Adjacent",
        "boundary": (
            Point3D(x=8, y=0, z=0), Point3D(x=12, y=0, z=0),
            Point3D(x=12, y=6, z=0), Point3D(x=8, y=6, z=0),
        ),
    })
    model = model.model_copy(update={"spaces": (first, second)})
    result = analyze_environmental_spatial_performance(model)
    assert result["spatial_adjacency"]["shared_boundary_edges"] == [{
        "source_space_id": "room-1", "target_space_id": "room-2",
        "shared_boundary_m": 6.0, "relationship": "SHARED_BOUNDARY",
        "traversable": False, "door_opening_ids": [],
    }]


def test_environmental_spatial_analysis_route_is_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/projects/{project_id}/environmental-spatial-analysis/generate" in paths
    assert "/api/v1/projects/{project_id}/environmental-spatial-analysis" in paths
