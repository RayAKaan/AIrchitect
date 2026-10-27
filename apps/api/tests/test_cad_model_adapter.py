from app.domains.cad.model_adapter import build_cad_request
from app.domains.model import ArchitecturalModel, Building, Level, Site, Space


def test_build_cad_request_is_deterministic_and_model_anchored() -> None:
    model = ArchitecturalModel(
        project_id="project",
        revision=1,
        site=Site(id="site", width_m=20, depth_m=20),
        buildings=(Building(id="building", name="Main", site_id="site"),),
        levels=(Level(id="level", building_id="building", name="Ground", elevation_m=0, height_m=3),),
        spaces=(
            Space(
                id="space",
                level_id="level",
                name="Living",
                boundary=((1, 1, 0), (5, 1, 0), (5, 4, 0), (1, 4, 0)),
            ),
        ),
    )
    first = build_cad_request(model, job_id="job")
    second = build_cad_request(model, job_id="job")
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.elements[0].source_reference
    assert first.elements[0].footprint.points == [(1.0, 1.0), (5.0, 1.0), (5.0, 4.0), (1.0, 4.0)]
    assert first.elements[0].height_m == 3
