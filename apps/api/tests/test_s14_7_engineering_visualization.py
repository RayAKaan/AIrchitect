from app.domains.engineering.structural_model import build_structural_model
from app.domains.engineering.visualization import build_structural_scene
from app.domains.model.schemas import ArchitecturalModel, Building, Level, ModelMetadata, Point3D, Site, Wall


def test_scene_is_renderer_neutral_and_source_bound():
    model = ArchitecturalModel(
        project_id="p", revision=1, metadata=ModelMetadata(), site=Site(id="site", width_m=20, depth_m=20),
        buildings=(Building(id="b", name="B", site_id="site"),),
        levels=(Level(id="l", building_id="b", name="L1", elevation_m=0, height_m=3),),
        walls=(Wall(id="w", level_id="l", name="W", start=Point3D(x=0,y=0,z=0), end=Point3D(x=4,y=0,z=0), thickness_m=.2, height_m=3),),
    )
    structural = build_structural_model(model)
    scene = build_structural_scene(structural)
    assert len(scene) == 1
    assert scene[0].id == "w"
    assert scene[0].primitive == "line"
    assert scene[0].start == (0, 0, 0)
    assert scene[0].end == (4, 0, 0)
