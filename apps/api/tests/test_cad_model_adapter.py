import pytest

from app.domains.cad.model_adapter import build_cad_request, build_semantic_cad_request
from app.domains.model import ArchitecturalModel, Building, Level, Point3D, Site, Space


def test_build_cad_request_is_deterministic_and_model_anchored() -> None:
    model = ArchitecturalModel(
        project_id="project",
        revision=1,
        site=Site(id="site", width_m=20, depth_m=20),
        buildings=(Building(id="building", name="Main", site_id="site"),),
        levels=(Level(id="level", building_id="building", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(id="space", level_id="level", name="Living", boundary=(
            Point3D(x=1,y=1,z=0), Point3D(x=5,y=1,z=0), Point3D(x=5,y=4,z=0), Point3D(x=1,y=4,z=0)
        )),),
    )
    first = build_cad_request(model, job_id="job")
    second = build_cad_request(model, job_id="job")
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.elements[0].source_reference
    assert first.elements[0].footprint.points == [(1.0, 1.0), (5.0, 1.0), (5.0, 4.0), (1.0, 4.0)]
    assert first.elements[0].height_m == 3


def _typed(value, unit=None, data_type="number"):
    return {"value": value, "unit": unit, "data_type": data_type}


def _semantic_wall(start_z=0.0):
    storey = {
        "id": "storey-1",
        "element_type": "Storey",
        "properties": {
            "level_number": _typed(1, "count", "integer"),
            "elevation_m": _typed(start_z, "m"),
        },
    }
    wall = {
        "id": "wall-1",
        "element_type": "Wall",
        "name": "North wall",
        "properties": {
            "start_m": _typed({"x": 0.0, "y": 0.0, "z": start_z}, "m", "vector3"),
            "end_m": _typed({"x": 5.0, "y": 0.0, "z": start_z}, "m", "vector3"),
            "length_m": _typed(5.0, "m"),
            "height_m": _typed(3.0, "m"),
            "thickness_m": _typed(0.2, "m"),
        },
    }
    semantic = {
        "project_id": "project-1",
        "project_version_id": "version-1",
        "source_world_model_hash": "a" * 64,
        "elements": [storey, wall],
        "relationships": [{
            "source_id": "storey-1",
            "relationship_type": "hosts_element",
            "target_id": "wall-1",
        }],
    }
    return {"building": {}, "properties": {}}, semantic


def test_semantic_wall_adapter_builds_real_prism_input_with_canonical_lineage():
    world, semantic = _semantic_wall(start_z=3.0)
    request = build_semantic_cad_request(world, semantic, job_id="wall-job")

    assert len(request.elements) == 1
    wall = request.elements[0]
    assert wall.id == "wall-1"
    assert wall.kind == "wall"
    assert wall.footprint.points == [
        (0.0, 0.1), (5.0, 0.1), (5.0, -0.1), (0.0, -0.1),
    ]
    assert wall.base_elevation_m == 3.0
    assert wall.height_m == 3.0
    assert wall.material_class == "architectural_wall"
    assert wall.source_reference == "a" * 64
    assert wall.metadata["semantic_element_id"] == "wall-1"
    assert wall.metadata["coordinate_system"] == "local_cartesian_z_up"


def test_semantic_wall_adapter_rejects_sloped_axis_until_supported():
    world, semantic = _semantic_wall()
    semantic["elements"][1]["properties"]["end_m"] = _typed(
        {"x": 5.0, "y": 0.0, "z": 0.5}, "m", "vector3"
    )
    with pytest.raises(ValueError, match="WALL_AXIS_NON_HORIZONTAL"):
        build_semantic_cad_request(world, semantic, job_id="sloped-wall")


def test_semantic_model_cad_route_is_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert (
        "/api/v1/projects/{project_id}/versions/{version_ref}/semantic-model/cad"
        in paths
    )


def test_semantic_wall_adapter_rejects_axis_length_mismatch():
    world, semantic = _semantic_wall()
    semantic["elements"][1]["properties"]["length_m"] = _typed(4.0, "m")
    with pytest.raises(ValueError, match="WALL_LENGTH_MISMATCH"):
        build_semantic_cad_request(world, semantic, job_id="mismatched-wall")
