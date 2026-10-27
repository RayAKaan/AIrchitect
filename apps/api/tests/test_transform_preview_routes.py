from app.domains.model.schemas import ArchitecturalModel, Building, Level, Point3D, Site, Wall
from app.domains.model.transform_routes import TransformPreviewRequest


def test_transform_preview_request_rejects_unknown_fields() -> None:
    payload = {
        "model": ArchitecturalModel(
            project_id="project-1",
            revision=1,
            site=Site(id="site", width_m=20, depth_m=20),
            buildings=(Building(id="building", name="Main", site_id="site"),),
            levels=(Level(id="level", building_id="building", name="Ground", elevation_m=0, height_m=3),),
            walls=(Wall(id="wall", level_id="level", name="Wall", start=Point3D(x=0, y=0, z=0), end=Point3D(x=5, y=0, z=0), thickness_m=0.2, height_m=3),),
        ),
        "element_id": "wall",
        "dx_m": 1,
        "dy_m": 0,
        "dz_m": 0,
        "extra": True,
    }
    try:
        TransformPreviewRequest.model_validate(payload)
    except Exception as exc:
        assert "extra" in str(exc)
    else:
        raise AssertionError("unknown request field was accepted")
