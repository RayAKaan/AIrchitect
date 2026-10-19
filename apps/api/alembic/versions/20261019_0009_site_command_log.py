"""idempotent site command log

Revision ID: 20261019_0009
Revises: 20261019_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20261019_0009"
down_revision = "20261019_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_command_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_version_id", sa.String(36), sa.ForeignKey("project_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command_id", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("command_type", sa.String(80), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("site_revision_id", sa.String(36), sa.ForeignKey("site_revisions.id"), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_site_command_project_idempotency"),
        sa.UniqueConstraint("project_id", "command_id", name="uq_site_command_project_command"),
    )
    op.create_index("ix_site_command_logs_project_id", "site_command_logs", ["project_id"])
    op.create_index("ix_site_command_logs_payload_hash", "site_command_logs", ["payload_hash"])


def downgrade() -> None:
    op.drop_index("ix_site_command_logs_payload_hash", table_name="site_command_logs")
    op.drop_index("ix_site_command_logs_project_id", table_name="site_command_logs")
    op.drop_table("site_command_logs")
