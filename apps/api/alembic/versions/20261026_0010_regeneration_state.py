"""durable regeneration lifecycle state

Revision ID: 20261026_0010
Revises: 20261019_0009
"""
from alembic import op
import sqlalchemy as sa

revision = "20261026_0010"
down_revision = "20261019_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regeneration_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_version_id", sa.String(36), sa.ForeignKey("project_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_version_id", sa.String(36), sa.ForeignKey("artifact_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_revision_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("output_revision_hash", sa.String(64), nullable=True),
        sa.Column("generation_key", sa.String(128), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("artifact_version_id", name="uq_regeneration_state_artifact"),
    )
    op.create_index("ix_regeneration_states_organization_id", "regeneration_states", ["organization_id"])
    op.create_index("ix_regeneration_states_project_id", "regeneration_states", ["project_id"])
    op.create_index("ix_regeneration_states_project_version_id", "regeneration_states", ["project_version_id"])
    op.create_index("ix_regeneration_states_artifact_version_id", "regeneration_states", ["artifact_version_id"])
    op.create_index("ix_regeneration_states_source_revision_hash", "regeneration_states", ["source_revision_hash"])
    op.create_index("ix_regeneration_states_status", "regeneration_states", ["status"])
    op.create_index("ix_regeneration_states_generation_key", "regeneration_states", ["generation_key"])


def downgrade() -> None:
    op.drop_index("ix_regeneration_states_generation_key", table_name="regeneration_states")
    op.drop_index("ix_regeneration_states_status", table_name="regeneration_states")
    op.drop_index("ix_regeneration_states_source_revision_hash", table_name="regeneration_states")
    op.drop_index("ix_regeneration_states_artifact_version_id", table_name="regeneration_states")
    op.drop_index("ix_regeneration_states_project_version_id", table_name="regeneration_states")
    op.drop_index("ix_regeneration_states_project_id", table_name="regeneration_states")
    op.drop_index("ix_regeneration_states_organization_id", table_name="regeneration_states")
    op.drop_table("regeneration_states")
