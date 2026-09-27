"""add_source_to_geometry_artifact

Revision ID: e72b4619cf31
Revises: 20260926_0006
Create Date: 2026-09-28 01:09:00.721727
"""
from alembic import op
import sqlalchemy as sa

revision = 'e72b4619cf31'
down_revision = '20260926_0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add source column to distinguish CAD_BREP from LEGACY_IR geometry artifacts
    # Default to LEGACY_IR for existing rows (design engine created)
    op.add_column(
        "geometry_artifacts",
        sa.Column("source", sa.String(24), nullable=False, server_default="LEGACY_IR"),
    )
    # Create index for filtering by source
    op.create_index(
        op.f("ix_geometry_artifacts_source"),
        "geometry_artifacts",
        ["source"],
        unique=False,
    )
    # Backfill: any artifact with cad_job_run_id in provenance_json is CAD_BREP
    # Use dialect-specific JSON extraction
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE geometry_artifacts
            SET source = 'CAD_BREP'
            WHERE provenance_json IS NOT NULL
            AND provenance_json::text LIKE '%"cad_job_run_id"%'
            """
        )
    else:
        # SQLite: json_extract or json ->>
        op.execute(
            """
            UPDATE geometry_artifacts
            SET source = 'CAD_BREP'
            WHERE provenance_json IS NOT NULL
            AND json_extract(provenance_json, '$.cad_job_run_id') IS NOT NULL
            """
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_geometry_artifacts_source"), table_name="geometry_artifacts")
    op.drop_column("geometry_artifacts", "source")