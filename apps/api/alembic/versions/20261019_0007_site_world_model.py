"""canonical site world model

Revision ID: 20261019_0007
Revises: e72b4619cf31
"""
from alembic import op
import sqlalchemy as sa

revision = "20261019_0007"
down_revision = "e72b4619cf31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("sites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_sites_organization_id", "sites", ["organization_id"])
    op.create_index("ix_sites_project_id", "sites", ["project_id"])
    op.create_table("site_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_version_id", sa.String(36), sa.ForeignKey("project_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False), sa.Column("parent_revision_id", sa.String(36), sa.ForeignKey("site_revisions.id")),
        sa.Column("boundary_geojson", sa.JSON, nullable=False), sa.Column("boundary_crs", sa.String(64), nullable=False),
        sa.Column("calculation_crs", sa.String(64), nullable=False), sa.Column("area_m2", sa.Float, nullable=False),
        sa.Column("perimeter_m", sa.Float, nullable=False), sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("validation_json", sa.JSON, nullable=False), sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("site_id", "revision", name="uq_site_revision"))
    for col in ("organization_id", "project_id", "project_version_id", "site_id", "content_hash"):
        op.create_index(f"ix_site_revisions_{col}", "site_revisions", [col])
    op.create_table("site_sources",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("site_revision_id", sa.String(36), sa.ForeignKey("site_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False), sa.Column("dataset", sa.String(200)), sa.Column("dataset_version", sa.String(120)),
        sa.Column("source_url", sa.String(1000)), sa.Column("retrieval_time", sa.DateTime(timezone=True), nullable=False), sa.Column("attribution", sa.Text),
        sa.Column("license", sa.String(160)), sa.Column("geographic_scope", sa.String(200)), sa.Column("resolution", sa.String(120)), sa.Column("raw_reference", sa.String(500)))
    op.create_index("ix_site_sources_site_revision_id", "site_sources", ["site_revision_id"])
    op.create_table("site_evidence",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("site_revision_id", sa.String(36), sa.ForeignKey("site_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("site_sources.id")), sa.Column("claim_type", sa.String(120), nullable=False),
        sa.Column("value_json", sa.JSON, nullable=False), sa.Column("confidence", sa.Float), sa.Column("status", sa.String(24), nullable=False), sa.Column("method", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_site_evidence_site_revision_id", "site_evidence", ["site_revision_id"])
    op.create_index("ix_site_evidence_source_id", "site_evidence", ["source_id"])
    op.create_table("site_layer_snapshots",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("site_revision_id", sa.String(36), sa.ForeignKey("site_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("layer_type", sa.String(64), nullable=False), sa.Column("provider", sa.String(120)), sa.Column("dataset_version", sa.String(120)),
        sa.Column("payload_json", sa.JSON, nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_site_layer_snapshots_site_revision_id", "site_layer_snapshots", ["site_revision_id"])
    op.create_table("site_constraints",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("site_revision_id", sa.String(36), sa.ForeignKey("site_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("constraint_type", sa.String(100), nullable=False), sa.Column("geometry_geojson", sa.JSON), sa.Column("value_json", sa.JSON, nullable=False),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("site_evidence.id")), sa.Column("status", sa.String(24), nullable=False))
    op.create_index("ix_site_constraints_site_revision_id", "site_constraints", ["site_revision_id"])
    op.create_table("site_observations",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("site_revision_id", sa.String(36), sa.ForeignKey("site_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("observation_type", sa.String(100), nullable=False), sa.Column("geometry_geojson", sa.JSON), sa.Column("value_json", sa.JSON, nullable=False),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("site_evidence.id")), sa.Column("status", sa.String(24), nullable=False))
    op.create_index("ix_site_observations_site_revision_id", "site_observations", ["site_revision_id"])


def downgrade() -> None:
    for table in ("site_observations", "site_constraints", "site_layer_snapshots", "site_evidence", "site_sources"):
        op.drop_table(table)
    for col in ("content_hash", "site_id", "project_version_id", "project_id", "organization_id"):
        op.drop_index(f"ix_site_revisions_{col}", table_name="site_revisions")
    op.drop_table("site_revisions")
    op.drop_index("ix_sites_project_id", table_name="sites")
    op.drop_index("ix_sites_organization_id", table_name="sites")
    op.drop_table("sites")
