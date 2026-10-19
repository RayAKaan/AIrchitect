from __future__ import annotations

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base, now, uid


class Provider(Base):
    __tablename__ = "providers"
    __table_args__ = (UniqueConstraint("provider_id", "capability", name="uq_provider_capability"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider_id: Mapped[str] = mapped_column(String(120), index=True)
    capability: Mapped[str] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    coverage_json: Mapped[dict] = mapped_column(JSON, default=dict)
    health_status: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ProviderTerms(Base):
    __tablename__ = "provider_terms"
    __table_args__ = (UniqueConstraint("provider_id", "capability", "version", name="uq_provider_terms_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider_id: Mapped[str] = mapped_column(String(120), index=True)
    capability: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(80))
    license: Mapped[str | None] = mapped_column(String(160), nullable=True)
    attribution_required: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_limit_json: Mapped[dict] = mapped_column(JSON, default=dict)
    commercial_use: Mapped[str] = mapped_column(String(80), default="UNKNOWN")
    caching_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    effective_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    review_due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProviderFetchLog(Base):
    __tablename__ = "provider_fetch_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider_id: Mapped[str] = mapped_column(String(120), index=True)
    capability: Mapped[str] = mapped_column(String(80))
    dataset: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dataset_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    fetched_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    terms_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="SUCCESS")
    raw_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    response_metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
