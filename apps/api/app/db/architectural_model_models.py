from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return str(uuid4())


class ArchitecturalModelRevision(Base):
    """Durable, immutable snapshot of the canonical architectural model."""

    __tablename__ = "architectural_model_revisions"
    __table_args__ = (
        UniqueConstraint("project_id", "revision", name="uq_architectural_model_project_revision"),
        UniqueConstraint("project_version_id", "revision", name="uq_architectural_model_version_revision"),
        Index("ix_architectural_model_project_current", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    project_version_id: Mapped[str] = mapped_column(
        ForeignKey("project_versions.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    model_hash: Mapped[str] = mapped_column(String(64), index=True)
    model_json: Mapped[dict] = mapped_column(JSON)
    parent_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("architectural_model_revisions.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(80), default="user")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
