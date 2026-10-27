import pytest

from app.domains.cad_exchange.ifc_semantics import project_architectural_semantics
from app.domains.model.schemas import ArchitecturalModel, Building, Level, ModelMetadata, Point3D, Site, Wall


def _model() -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="p",
        revision=4,
        metadata=ModelMetadata(),
        site=Site(id="site", width_m=20, depth_m=20),
        buildings=(Building(id="b", name="B", site_id="site"),),
        levels=(Level(id="l", building_id="b", name="L1", elevation_m=3, height_m=3),),
        walls=(Wall(id="w", level_id="l", name="Wall", start=Point3D(x=0,y=0,z=3), end=Point3D(x=5,y=0,z=3), thickness_m=.2, height_m=3),),
    )


def test_projection_is_semantic_and_deterministic():
    first = project_architectural_semantics(_model())
    second = project_architectural_semantics(_model())
    assert first == second
    assert [entity.ifc_class for entity in first.entities] == ["IfcBuildingStorey", "IfcWall"]
    assert ("CONTAINED_IN", "w", "l") in first.relationships
    assert len(first.model_hash) == 64


def test_only_ifc4_is_supported():
    with pytest.raises(ValueError, match="IFC_SCHEMA_UNSUPPORTED"):
        project_architectural_semantics(_model(), schema="IFC2X3")
