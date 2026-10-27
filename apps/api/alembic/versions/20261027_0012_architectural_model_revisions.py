"""durable architectural model revisions

Revision ID: 20261027_0012
Revises: 20261026_0011
"""
from alembic import op
import sqlalchemy as sa

revision = "20261027_0012"
down_revision = "20261026_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "architectural_model_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_version_id", sa.String(36), sa.ForeignKey("project_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("model_hash", sa.String(64), nullable=False),
        sa.Column("model_json", sa.JSON(), nullable=False),
        sa.Column("parent_revision_id", sa.String(36), sa.ForeignKey("architectural_model_revisions.id"), nullable=True),
        sa.Column("source", sa.String(80), nullable=False, server_default="user"),
        sa.Column("change_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "revision", name="uq_architectural_model_project_revision"),
        sa.UniqueConstraint("project_version_id", "revision", name="uq_architectural_model_version_revision"),
    )
    op.create_index("ix_architectural_model_revisions_organization_id", "architectural_model_revisions", ["organization_id"])
    op.create_index("ix_architectural_model_revisions_project_id", "architectural_model_revisions", ["project_id"])
    op.create_index("ix_architectural_model_revisions_project_version_id", "architectural_model_revisions", ["project_version_id"])
    op.create_index("ix_architectural_model_revisions_model_hash", "architectural_model_revisions", ["model_hash"])
    op.create_index("ix_architectural_model_project_current", "architectural_model_revisions", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_architectural_model_project_current", table_name="architectural_model_revisions")
    op.drop_index("ix_architectural_model_revisions_model_hash", table_name="architectural_model_revisions")
    op.drop_index("ix_architectural_model_revisions_project_version_id", table_name="architectural_model_revisions")
    op.drop_index("ix_architectural_model_revisions_project_id", table_name="architectural_model_revisions")
    op.drop_index("ix_architectural_model_revisions_organization_id", table_name="architectural_model_revisions")
    op.drop_table("architectural_model_revisions")
