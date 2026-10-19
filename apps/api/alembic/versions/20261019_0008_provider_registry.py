"""provider adapter registry and terms lineage

Revision ID: 20261019_0008
Revises: 20261019_0007
"""
from alembic import op
import sqlalchemy as sa

revision = "20261019_0008"
down_revision = "20261019_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("providers",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("provider_id", sa.String(120), nullable=False),
        sa.Column("capability", sa.String(80), nullable=False), sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("coverage_json", sa.JSON, nullable=False), sa.Column("health_status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_id", "capability", name="uq_provider_capability"))
    op.create_index("ix_providers_provider_id", "providers", ["provider_id"])
    op.create_table("provider_terms",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("provider_id", sa.String(120), nullable=False),
        sa.Column("capability", sa.String(80), nullable=False), sa.Column("version", sa.String(80), nullable=False),
        sa.Column("license", sa.String(160)), sa.Column("attribution_required", sa.Boolean, nullable=False),
        sa.Column("rate_limit_json", sa.JSON, nullable=False), sa.Column("commercial_use", sa.String(80), nullable=False),
        sa.Column("caching_allowed", sa.Boolean, nullable=False), sa.Column("source_url", sa.String(1000)),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False), sa.Column("review_due_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("provider_id", "capability", "version", name="uq_provider_terms_version"))
    op.create_index("ix_provider_terms_provider_id", "provider_terms", ["provider_id"])
    op.create_table("provider_fetch_logs",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("provider_id", sa.String(120), nullable=False),
        sa.Column("capability", sa.String(80), nullable=False), sa.Column("dataset", sa.String(200)), sa.Column("dataset_version", sa.String(120)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False), sa.Column("source_url", sa.String(1000)),
        sa.Column("terms_version", sa.String(80)), sa.Column("status", sa.String(24), nullable=False), sa.Column("raw_reference", sa.String(500)),
        sa.Column("response_metadata_json", sa.JSON, nullable=False))
    op.create_index("ix_provider_fetch_logs_provider_id", "provider_fetch_logs", ["provider_id"])


def downgrade() -> None:
    op.drop_index("ix_provider_fetch_logs_provider_id", table_name="provider_fetch_logs")
    op.drop_table("provider_fetch_logs")
    op.drop_index("ix_provider_terms_provider_id", table_name="provider_terms")
    op.drop_table("provider_terms")
    op.drop_index("ix_providers_provider_id", table_name="providers")
    op.drop_table("providers")
