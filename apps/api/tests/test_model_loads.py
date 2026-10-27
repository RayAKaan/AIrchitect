from app.domains.engineering.model_loads import derive_preliminary_loads
from app.domains.model import ArchitecturalModel, Building, Level, Point3D, Site, Space


def test_preliminary_loads_are_area_based_and_deterministic() -> None:
    model = ArchitecturalModel(
        project_id="p",
        revision=1,
        site=Site(id="s", width_m=20, depth_m=20),
        buildings=(Building(id="b", name="Main", site_id="s"),),
        levels=(Level(id="l", building_id="b", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(id="room", level_id="l", name="Room", boundary=(
            Point3D(x=0, y=0, z=0), Point3D(x=5, y=0, z=0),
            Point3D(x=5, y=4, z=0), Point3D(x=0, y=4, z=0),
        )),),
    )
    result = derive_preliminary_loads(model)
    assert result.is_screening_only is True
    assert result.spaces[0].area_m2 == 20
    assert result.spaces[0].dead_load_kn == 30
    assert result.spaces[0].live_load_kn == 40
    assert result.spaces[0].factored_load_kn == 100
    assert result.total_factored_load_kn == 100
    assert result.model_hash == derive_preliminary_loads(model).model_hash
