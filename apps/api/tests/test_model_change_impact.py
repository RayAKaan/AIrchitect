from app.domains.model import ArchitecturalModel, Building, Level, Point3D, Site, Space
from app.domains.model.change_impact import plan_change_impact


def _model(name: str = "Room") -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="p", revision=1, site=Site(id="s", width_m=20, depth_m=20),
        buildings=(Building(id="b", name="Main", site_id="s"),),
        levels=(Level(id="l", building_id="b", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(id="room", level_id="l", name=name, boundary=(
            Point3D(x=1,y=1,z=0), Point3D(x=5,y=1,z=0), Point3D(x=5,y=4,z=0), Point3D(x=1,y=4,z=0)
        )),),
    )


def test_changed_space_propagates_to_dependent_artifacts() -> None:
    result = plan_change_impact(_model(), _model("Changed Room"))
    assert len(result.changed_elements) == 1
    assert result.changed_elements[0].element_id == "room"
    assert result.changed_elements[0].change_type == "updated"
    assert result.affected_elements == ("room",)
    assert result.invalidated_artifacts == ("geometry", "quantities", "cost", "engineering", "regulatory")
    assert result.previous_hash != result.current_hash


def test_identical_models_have_no_invalidations() -> None:
    result = plan_change_impact(_model(), _model())
    assert result.changed_elements == ()
    assert result.affected_elements == ()
    assert result.invalidated_artifacts == ()
