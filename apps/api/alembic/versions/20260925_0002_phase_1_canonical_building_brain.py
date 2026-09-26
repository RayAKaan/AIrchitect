"""Phase 1 canonical building brain.

Revision ID: 20260925_0002
Revises: 20260925_0001
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "20260925_0002"
down_revision = "20260925_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("building_briefs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("project_version_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("structured_json", sa.JSON(), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_version_id"], ["project_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_version_id", "revision", name="uq_brief_revision"),
    )
    op.create_index("ix_building_briefs_organization_id", "building_briefs", ["organization_id"])
    op.create_index("ix_building_briefs_project_id", "building_briefs", ["project_id"])
    op.create_index("ix_building_briefs_project_version_id", "building_briefs", ["project_version_id"])

    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("project_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("project_version_id", sa.String(36), nullable=True))
        batch.create_index("ix_audit_events_project_id", ["project_id"])
        batch.create_index("ix_audit_events_project_version_id", ["project_version_id"])
    with op.batch_alter_table("project_versions") as batch:
        batch.add_column(sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("source", sa.String(80), nullable=False, server_default="legacy_migration"))
        batch.add_column(sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
        batch.add_column(sa.Column("idempotency_key", sa.String(200), nullable=True))
        batch.create_unique_constraint("uq_project_version_idempotency", ["project_id", "idempotency_key"])
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("current_version_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
        batch.create_index("ix_projects_current_version_id", ["current_version_id"])
        batch.create_foreign_key("fk_projects_current_version", "project_versions", ["current_version_id"], ["id"])
    # Backfill the canonical pointer deterministically for pre-Phase-1 projects.
    bind = op.get_bind()
    projects = sa.table("projects", sa.column("id"), sa.column("current_version_id"))
    versions = sa.table("project_versions", sa.column("id"), sa.column("project_id"), sa.column("version"), sa.column("status"))
    for project_id in [row[0] for row in bind.execute(sa.select(projects.c.id))]:
        latest_row = bind.execute(sa.select(versions.c.id, versions.c.status).where(
            versions.c.project_id == project_id).order_by(versions.c.version.desc()).limit(1)).first()
        if latest_row:
            latest, old_status = latest_row
            bind.execute(projects.update().where(projects.c.id == project_id).values(current_version_id=latest))
            bind.execute(versions.update().where((versions.c.project_id == project_id) & (versions.c.id != latest)).values(status="SUPERSEDED"))
            current_status = "DRAFT" if str(old_status).lower() == "draft" else "COMMITTED"
            bind.execute(versions.update().where(versions.c.id == latest).values(status=current_status))
    with op.batch_alter_table("requirements") as batch:
        batch.add_column(sa.Column("raw_value_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("value_type", sa.String(24), nullable=False, server_default="string"))
        batch.add_column(sa.Column("source_type", sa.String(40), nullable=False, server_default="LEGACY"))
        batch.add_column(sa.Column("source_reference", sa.String(500), nullable=True))
        batch.add_column(sa.Column("extraction_method", sa.String(100), nullable=False, server_default="legacy"))
        batch.add_column(sa.Column("confirmed_by", sa.String(36), nullable=True))
        batch.add_column(sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
        batch.create_foreign_key("fk_requirements_confirmed_by_users", "users", ["confirmed_by"], ["id"])
    with op.batch_alter_table("world_model_revisions") as batch:
        batch.add_column(sa.Column("source", sa.String(80), nullable=False, server_default="legacy_migration"))
        batch.add_column(sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    with op.batch_alter_table("world_model_revisions") as batch:
        batch.drop_column("metadata_json")
        batch.drop_column("source")
    with op.batch_alter_table("requirements") as batch:
        batch.drop_constraint("fk_requirements_confirmed_by_users", type_="foreignkey")
        for name in ("updated_at", "confirmed_at", "confirmed_by", "extraction_method", "source_reference",
                     "source_type", "value_type", "raw_value_json"):
            batch.drop_column(name)
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_projects_current_version", type_="foreignkey")
        batch.drop_index("ix_projects_current_version_id")
        batch.drop_column("metadata_json")
        batch.drop_column("current_version_id")
    with op.batch_alter_table("project_versions") as batch:
        batch.drop_constraint("uq_project_version_idempotency", type_="unique")
        for name in ("idempotency_key", "metadata_json", "source", "revision_number"):
            batch.drop_column(name)
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_index("ix_audit_events_project_version_id")
        batch.drop_index("ix_audit_events_project_id")
        batch.drop_column("project_version_id")
        batch.drop_column("project_id")
    op.drop_index("ix_building_briefs_project_version_id", table_name="building_briefs")
    op.drop_index("ix_building_briefs_project_id", table_name="building_briefs")
    op.drop_index("ix_building_briefs_organization_id", table_name="building_briefs")
    op.drop_table("building_briefs")
