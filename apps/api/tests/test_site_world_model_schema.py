from sqlalchemy import inspect

from app.db.site_models import Site, SiteConstraint, SiteEvidence, SiteLayerSnapshot, SiteObservation, SiteRevision, SiteSource


def test_site_world_model_declares_all_canonical_entities() -> None:
    assert {model.__tablename__ for model in (Site, SiteRevision, SiteSource, SiteEvidence, SiteLayerSnapshot, SiteConstraint, SiteObservation)} == {
        "sites", "site_revisions", "site_sources", "site_evidence", "site_layer_snapshots", "site_constraints", "site_observations"
    }


def test_site_revision_keeps_interchange_and_calculation_crs_separate() -> None:
    columns = {column.name for column in inspect(SiteRevision).columns}
    assert {"boundary_crs", "calculation_crs", "boundary_geojson", "content_hash", "parent_revision_id"} <= columns
