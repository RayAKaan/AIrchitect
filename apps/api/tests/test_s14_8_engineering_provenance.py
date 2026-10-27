from app.domains.engineering.model_loads import derive_preliminary_loads
from app.domains.engineering.provenance import build_provenance
from app.domains.engineering.structural_model import build_structural_model
from app.domains.model.schemas import ArchitecturalModel, Building, Level, ModelMetadata, Point3D, Site, Wall


def test_provenance_contains_full_source_chain():
    model = ArchitecturalModel(
        project_id="p", revision=3, metadata=ModelMetadata(), site=Site(id="site", width_m=20, depth_m=20),
        buildings=(Building(id="b", name="B", site_id="site"),),
        levels=(Level(id="l", building_id="b", name="L1", elevation_m=0, height_m=3),),
        walls=(Wall(id="w", level_id="l", name="W", start=Point3D(x=0,y=0,z=0), end=Point3D(x=4,y=0,z=0), thickness_m=.2, height_m=3),),
    )
    structural = build_structural_model(model)
    loads = derive_preliminary_loads(model)
    provenance = build_provenance(model=model, structural=structural, loads=loads, result_payload={"status": "SCREENING_VALID"}, status="SCREENING_VALID")
    assert provenance.model_revision == 3
    assert all(len(value) == 64 for value in (provenance.model_hash, provenance.geometry_hash, provenance.structural_hash, provenance.load_hash, provenance.result_hash))
