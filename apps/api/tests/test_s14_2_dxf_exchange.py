from app.domains.cad_exchange.dxf import dxf_metadata, render_dxf
from app.domains.model.schemas import ArchitecturalModel, Building, Level, ModelMetadata, Point3D, Site, Wall


def _model() -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="p",
        revision=2,
        metadata=ModelMetadata(),
        site=Site(id="site", width_m=20, depth_m=20),
        buildings=(Building(id="b", name="B", site_id="site"),),
        levels=(Level(id="l", building_id="b", name="L1", elevation_m=0, height_m=3),),
        walls=(
            Wall(
                id="w",
                level_id="l",
                name="Wall",
                start=Point3D(x=0, y=0, z=0),
                end=Point3D(x=5, y=0, z=0),
                thickness_m=0.2,
                height_m=3,
            ),
        ),
    )


def test_dxf_is_deterministic() -> None:
    first = render_dxf(_model())
    assert first == render_dxf(_model())
    assert b"AC1009" in first
    assert b"AI_WALL" in first
    assert first.endswith(b"0\nEOF\n")


def test_metadata_binds_revision() -> None:
    metadata = dxf_metadata(_model())
    assert metadata["model_revision"] == 2
    assert metadata["wall_count"] == 1
    assert len(metadata["model_hash"]) == 64
