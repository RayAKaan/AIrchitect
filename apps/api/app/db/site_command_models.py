from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models import Base, now, uid


class SiteCommandLog(Base):
    __tablename__ = "site_command_logs"
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_site_command_project_idempotency"),
        UniqueConstraint("project_id", "command_id", name="uq_site_command_project_command"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    command_id: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    command_type: Mapped[str] = mapped_column(String(80))
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default="COMMITTED")
    site_revision_id: Mapped[str | None] = mapped_column(ForeignKey("site_revisions.id"), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
