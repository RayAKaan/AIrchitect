from app.domains.engineering.structural_model import build_structural_model
from app.domains.model.schemas import ArchitecturalModel, Building, Level, ModelMetadata, Point3D, Site, Wall


def test_structural_model_is_bound_to_canonical_hash_and_has_members():
    model = ArchitecturalModel(
        project_id="p",
        revision=1,
        metadata=ModelMetadata(),
        site=Site(id="site", width_m=20, depth_m=20),
        buildings=(Building(id="b", name="B", site_id="site"),),
        levels=(Level(id="l", building_id="b", name="L1", elevation_m=0, height_m=3),),
        walls=(Wall(id="w", level_id="l", name="W", start=Point3D(x=0,y=0,z=0), end=Point3D(x=4,y=0,z=0), thickness_m=.2, height_m=3),),
    )
    result = build_structural_model(model)
    assert result.screening_only is True
    assert len(result.nodes) == 2
    assert len(result.members) == 1
    assert result.members[0].length_m == 4
    assert len(result.model_hash) == 64
