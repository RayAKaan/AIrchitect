from __future__ import annotations

from datetime import datetime
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base, now, uid


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200), default="Site")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SiteRevision(Base):
    __tablename__ = "site_revisions"
    __table_args__ = (UniqueConstraint("site_id", "revision", name="uq_site_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    parent_revision_id: Mapped[str | None] = mapped_column(ForeignKey("site_revisions.id"), nullable=True)
    boundary_geojson: Mapped[dict] = mapped_column(JSON)
    boundary_crs: Mapped[str] = mapped_column(String(64), default="EPSG:4326")
    calculation_crs: Mapped[str] = mapped_column(String(64), default="LOCAL_METRIC")
    area_m2: Mapped[float] = mapped_column(Float)
    perimeter_m: Mapped[float] = mapped_column(Float)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    validation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SiteSource(Base):
    __tablename__ = "site_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site_revision_id: Mapped[str] = mapped_column(ForeignKey("site_revisions.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(120))
    dataset: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dataset_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    retrieval_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(String(160), nullable=True)
    geographic_scope: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(120), nullable=True)
    raw_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SiteEvidence(Base):
    __tablename__ = "site_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site_revision_id: Mapped[str] = mapped_column(ForeignKey("site_revisions.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("site_sources.id"), nullable=True, index=True)
    claim_type: Mapped[str] = mapped_column(String(120))
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    method: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SiteLayerSnapshot(Base):
    __tablename__ = "site_layer_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site_revision_id: Mapped[str] = mapped_column(ForeignKey("site_revisions.id", ondelete="CASCADE"), index=True)
    layer_type: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dataset_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SiteConstraint(Base):
    __tablename__ = "site_constraints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site_revision_id: Mapped[str] = mapped_column(ForeignKey("site_revisions.id", ondelete="CASCADE"), index=True)
    constraint_type: Mapped[str] = mapped_column(String(100))
    geometry_geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("site_evidence.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="UNKNOWN")


class SiteObservation(Base):
    __tablename__ = "site_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    site_revision_id: Mapped[str] = mapped_column(ForeignKey("site_revisions.id", ondelete="CASCADE"), index=True)
    observation_type: Mapped[str] = mapped_column(String(100))
    geometry_geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("site_evidence.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
