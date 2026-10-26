from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> str:
    return str(uuid4())


class RegenerationStateRecord(Base):
    """Durable projection of the authoritative regeneration lifecycle.

    The row is keyed to an artifact version. Source and output revisions are
    deliberately stored separately so stale work can never be mistaken for a
    current artifact merely because a job completed.
    """

    __tablename__ = "regeneration_states"
    __table_args__ = (
        UniqueConstraint("artifact_version_id", name="uq_regeneration_state_artifact"),
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
    artifact_version_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_versions.id", ondelete="CASCADE"), index=True
    )
    source_revision_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    output_revision_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_key: Mapped[str] = mapped_column(String(128), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
