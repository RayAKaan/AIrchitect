from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.site_models import Site, SiteEvidence, SiteLayerSnapshot, SiteRevision
from app.domains.site.service import _materialize_stale_derived_state


@pytest.mark.asyncio
async def test_materialize_stale_derived_state_marks_only_historical_rows_stale() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        site = Site(organization_id="org", project_id="project", created_by="user")
        session.add(site)
        await session.flush()
        old = SiteRevision(
            organization_id="org", project_id="project", project_version_id="version", site_id=site.id,
            revision=1, boundary_geojson={"type": "Polygon", "coordinates": []}, boundary_crs="EPSG:4326",
            calculation_crs="LOCAL_METRIC", area_m2=10, perimeter_m=10, content_hash="a" * 64, created_by="user",
        )
        current = SiteRevision(
            organization_id="org", project_id="project", project_version_id="version", site_id=site.id,
            revision=2, boundary_geojson={"type": "Polygon", "coordinates": []}, boundary_crs="EPSG:4326",
            calculation_crs="LOCAL_METRIC", area_m2=12, perimeter_m=11, content_hash="b" * 64, created_by="user",
        )
        session.add_all([old, current])
        await session.flush()
        old_snapshot = SiteLayerSnapshot(site_revision_id=old.id, layer_type="ANALYSIS", status="SUPPORTED")
        current_snapshot = SiteLayerSnapshot(site_revision_id=current.id, layer_type="ANALYSIS", status="SUPPORTED")
        old_evidence = SiteEvidence(site_revision_id=old.id, claim_type="site_analysis", status="SUPPORTED")
        current_evidence = SiteEvidence(site_revision_id=current.id, claim_type="site_analysis", status="SUPPORTED")
        session.add_all([old_snapshot, current_snapshot, old_evidence, current_evidence])
        await session.flush()

        await _materialize_stale_derived_state(session, site.id, current.id)

        assert old_snapshot.status == "STALE"
        assert old_evidence.status == "STALE"
        assert current_snapshot.status == "SUPPORTED"
        assert current_evidence.status == "SUPPORTED"

    await engine.dispose()
