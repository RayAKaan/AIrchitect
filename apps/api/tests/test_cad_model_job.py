import pytest

from app.domains.cad.model_job import build_canonical_cad_job
from app.domains.model import ArchitecturalModel, Building, Level, Site, Space


def test_build_canonical_cad_job_contains_matching_request_and_provenance() -> None:
    model = ArchitecturalModel(
        project_id="project",
        revision=4,
        site=Site(id="site", width_m=20, depth_m=20),
        buildings=(Building(id="building", name="Main", site_id="site"),),
        levels=(Level(id="level", building_id="building", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(id="space", level_id="level", name="Living", boundary=((1, 1, 0), (5, 1, 0), (5, 4, 0), (1, 4, 0))),),
    )
    job = build_canonical_cad_job(model, job_id="job-4")
    assert job.request.job_id == "job-4"
    assert job.provenance.model_revision == 4
    assert job.provenance.model_hash == job.request.elements[0].source_reference
    assert job.provenance.element_ids == ("space",)


def test_blank_job_id_is_rejected() -> None:
    model = ArchitecturalModel(project_id="p", revision=1, site=Site(id="s", width_m=10, depth_m=10))
    with pytest.raises(ValueError, match="job_id"):
        build_canonical_cad_job(model, job_id=" ")
