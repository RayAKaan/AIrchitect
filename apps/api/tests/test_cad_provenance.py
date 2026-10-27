import pytest

from app.domains.cad.model_adapter import build_cad_request
from app.domains.cad.provenance import build_input_provenance
from app.domains.model import ArchitecturalModel, Building, Level, Point3D, Site, Space


def _model(revision: int = 1) -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="project",
        revision=revision,
        site=Site(id="site", width_m=20, depth_m=20),
        buildings=(Building(id="building", name="Main", site_id="site"),),
        levels=(Level(id="level", building_id="building", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(id="space", level_id="level", name="Living", boundary=(
            Point3D(x=1, y=1, z=0), Point3D(x=5, y=1, z=0),
            Point3D(x=5, y=4, z=0), Point3D(x=1, y=4, z=0),
        )),),
    )


def test_provenance_is_stable_and_contains_model_identity() -> None:
    model = _model()
    request = build_cad_request(model)
    first = build_input_provenance(model, request)
    second = build_input_provenance(model, request)
    assert first == second
    assert first.project_id == "project"
    assert first.model_revision == 1
    assert len(first.model_hash) == 64
    assert len(first.request_hash) == 64
    assert first.element_ids == ("space",)


def test_provenance_rejects_cross_revision_request() -> None:
    model = _model(1)
    other = _model(2)
    request = build_cad_request(other)
    with pytest.raises(ValueError, match="different canonical model revision"):
        build_input_provenance(model, request)
