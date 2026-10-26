"""durable regeneration jobs

Revision ID: 20261026_0011
Revises: 20261026_0010
"""
from alembic import op
import sqlalchemy as sa

revision = "20261026_0011"
down_revision = "20261026_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regeneration_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("regeneration_state_id", sa.String(36), sa.ForeignKey("regeneration_states.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_version_id", sa.String(36), sa.ForeignKey("project_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_version_id", sa.String(36), sa.ForeignKey("artifact_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_revision_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(120), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("regeneration_state_id", "source_revision_hash", name="uq_regeneration_job_revision"),
    )
    op.create_index("ix_regeneration_jobs_regeneration_state_id", "regeneration_jobs", ["regeneration_state_id"])
    op.create_index("ix_regeneration_jobs_organization_id", "regeneration_jobs", ["organization_id"])
    op.create_index("ix_regeneration_jobs_project_id", "regeneration_jobs", ["project_id"])
    op.create_index("ix_regeneration_jobs_project_version_id", "regeneration_jobs", ["project_version_id"])
    op.create_index("ix_regeneration_jobs_artifact_version_id", "regeneration_jobs", ["artifact_version_id"])
    op.create_index("ix_regeneration_jobs_source_revision_hash", "regeneration_jobs", ["source_revision_hash"])
    op.create_index("ix_regeneration_jobs_status", "regeneration_jobs", ["status"])
    op.create_index("ix_regeneration_jobs_available_at", "regeneration_jobs", ["available_at"])


def downgrade() -> None:
    op.drop_index("ix_regeneration_jobs_available_at", table_name="regeneration_jobs")
    op.drop_index("ix_regeneration_jobs_status", table_name="regeneration_jobs")
    op.drop_index("ix_regeneration_jobs_source_revision_hash", table_name="regeneration_jobs")
    op.drop_index("ix_regeneration_jobs_artifact_version_id", table_name="regeneration_jobs")
    op.drop_index("ix_regeneration_jobs_project_version_id", table_name="regeneration_jobs")
    op.drop_index("ix_regeneration_jobs_project_id", table_name="regeneration_jobs")
    op.drop_index("ix_regeneration_jobs_organization_id", table_name="regeneration_jobs")
    op.drop_index("ix_regeneration_jobs_regeneration_state_id", table_name="regeneration_jobs")
    op.drop_table("regeneration_jobs")
