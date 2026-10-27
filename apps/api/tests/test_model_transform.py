import pytest

from app.domains.model.schemas import ArchitecturalModel, Building, Level, Point3D, Site, Wall
from app.domains.model.transform import TranslateElement, translate_element


def model() -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="project-1",
        revision=1,
        site=Site(id="site", width_m=20, depth_m=20),
        buildings=(Building(id="building", name="Main", site_id="site"),),
        levels=(Level(id="level", building_id="building", name="Ground", elevation_m=0, height_m=3),),
        walls=(Wall(id="wall", level_id="level", name="Wall", start=Point3D(x=0, y=0, z=0), end=Point3D(x=5, y=0, z=0), thickness_m=0.2, height_m=3),),
    )


def test_translation_is_pure_and_increments_revision() -> None:
    original = model()
    updated = translate_element(original, TranslateElement("wall", 2, 3, 0))
    assert original.revision == 1
    assert updated.revision == 2
    assert updated.walls[0].start == Point3D(x=2, y=3, z=0)
    assert updated.walls[0].end == Point3D(x=7, y=3, z=0)


def test_unknown_element_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a translatable"):
        translate_element(model(), TranslateElement("missing", 1, 0, 0))
