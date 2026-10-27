from datetime import datetime, timezone

from app.domains.model.persistence import model_summary
from app.domains.model.schemas import ArchitecturalModel, Building, Point3D, Site


def make_model(revision: int = 1) -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="project-1",
        revision=revision,
        site=Site(id="site-1", width_m=20, depth_m=30, origin=Point3D(x=0, y=0, z=0)),
        buildings=(Building(id="building-1", name="Main", site_id="site-1"),),
    )


def test_model_summary_is_json_stable() -> None:
    model = make_model()

    class Row:
        revision = 1
        model_hash = "a" * 64
        project_version_id = "version-1"
        parent_revision_id = None
        source = "user"
        change_summary = "Initial model"
        created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    summary = model_summary(Row(), model)
    assert summary["revision"] == 1
    assert summary["model"]["project_id"] == "project-1"
    assert summary["created_at"].startswith("2026-01-01T00:00:00")
