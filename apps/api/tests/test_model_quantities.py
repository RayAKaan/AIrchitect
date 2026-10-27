from app.domains.estimates.model_quantities import derive_model_quantities
from app.domains.model import ArchitecturalModel, Building, Level, Point3D, Site, Slab, Space, Wall


def test_model_quantities_are_derived_from_canonical_state() -> None:
    model = ArchitecturalModel(
        project_id="p",
        revision=1,
        site=Site(id="s", width_m=20, depth_m=20),
        buildings=(Building(id="b", name="Main", site_id="s"),),
        levels=(Level(id="l", building_id="b", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(id="room", level_id="l", name="Room", boundary=(
            Point3D(x=0, y=0, z=0), Point3D(x=4, y=0, z=0),
            Point3D(x=4, y=5, z=0), Point3D(x=0, y=5, z=0),
        )),),
        walls=(Wall(id="wall", level_id="l", name="Wall", start=Point3D(x=0,y=0,z=0), end=Point3D(x=4,y=0,z=0), thickness_m=.2, height_m=3, space_ids=("room",)),),
        slabs=(Slab(id="slab", level_id="l", name="Slab", boundary=(
            Point3D(x=0,y=0,z=0), Point3D(x=4,y=0,z=0), Point3D(x=4,y=5,z=0), Point3D(x=0,y=5,z=0)
        ), thickness_m=.2),),
    )
    quantities = derive_model_quantities(model)
    assert quantities.floor_area_m2 == 20
    assert quantities.slab_volume_m3 == 4
    assert quantities.wall_surface_area_m2 > 0
    assert quantities.conceptual_cost > 0
    assert quantities.is_conceptual is True
