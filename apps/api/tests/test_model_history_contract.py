from app.domains.model.schemas import ArchitecturalModel, Building, Level, Point3D, Site, Space


def test_revert_target_becomes_new_revision_without_mutating_history() -> None:
    target = ArchitecturalModel(
        project_id="project-1",
        revision=3,
        site=Site(id="site-1", width_m=20, depth_m=20),
        buildings=(Building(id="building-1", name="Main", site_id="site-1"),),
        levels=(Level(id="level-1", building_id="building-1", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(
            id="space-1", level_id="level-1", name="Room",
            boundary=(Point3D(x=0, y=0, z=0), Point3D(x=4, y=0, z=0), Point3D(x=4, y=3, z=0)),
        ),),
    )
    reverted = target.model_copy(update={"revision": 5})
    assert target.revision == 3
    assert reverted.revision == 5
    assert reverted.model_dump(mode="json", exclude={"revision"}) == target.model_dump(mode="json", exclude={"revision"})
