"""Phase 2 computational design and Geometry IR.

Revision ID: 20260925_0003
Revises: 20260925_0002
"""
from alembic import op
import sqlalchemy as sa

revision="20260925_0003"
down_revision="20260925_0002"
branch_labels=None
depends_on=None


def upgrade()->None:
    op.create_table("design_generation_runs",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("project_id",sa.String(36),sa.ForeignKey("projects.id",ondelete="CASCADE"),nullable=False),
        sa.Column("project_version_id",sa.String(36),sa.ForeignKey("project_versions.id",ondelete="CASCADE"),nullable=False),
        sa.Column("world_model_revision_id",sa.String(36),sa.ForeignKey("world_model_revisions.id"),nullable=False),
        sa.Column("world_model_hash",sa.String(64),nullable=False),sa.Column("generation_key",sa.String(64),nullable=False),
        sa.Column("engine_version",sa.String(40),nullable=False),sa.Column("config_version",sa.String(40),nullable=False),
        sa.Column("status",sa.String(24),nullable=False),sa.Column("progress_json",sa.JSON(),nullable=False),
        sa.Column("generated_alternative_ids_json",sa.JSON(),nullable=False),sa.Column("error_code",sa.String(80)),
        sa.Column("error_message",sa.Text()),sa.Column("requested_by",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("requested_at",sa.DateTime(timezone=True),nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True)),
        sa.UniqueConstraint("project_version_id","generation_key",name="uq_design_generation_key"))
    for column in ("organization_id","project_id","project_version_id","status","world_model_hash","world_model_revision_id"):
        op.create_index(f"ix_design_generation_runs_{column}","design_generation_runs",[column])
    op.create_table("design_constraints",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("generation_run_id",sa.String(36),sa.ForeignKey("design_generation_runs.id",ondelete="CASCADE"),nullable=False),
        sa.Column("project_version_id",sa.String(36),sa.ForeignKey("project_versions.id",ondelete="CASCADE"),nullable=False),
        sa.Column("world_model_revision_id",sa.String(36),sa.ForeignKey("world_model_revisions.id"),nullable=False),
        sa.Column("source_reference",sa.String(160),nullable=False),sa.Column("parameter",sa.String(100),nullable=False),
        sa.Column("value_json",sa.JSON()),sa.Column("unit",sa.String(40)),sa.Column("classification",sa.String(24),nullable=False),
        sa.Column("operator",sa.String(24),nullable=False),sa.Column("severity",sa.String(24),nullable=False),
        sa.Column("rationale",sa.Text(),nullable=False),sa.Column("provenance_json",sa.JSON(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    for column in ("generation_run_id","parameter","project_version_id","world_model_revision_id"):
        op.create_index(f"ix_design_constraints_{column}","design_constraints",[column])
    with op.batch_alter_table("design_alternatives") as batch:
        batch.add_column(sa.Column("world_model_revision_id",sa.String(36),nullable=True))
        batch.add_column(sa.Column("generation_run_id",sa.String(36),nullable=True))
        batch.add_column(sa.Column("strategy_id",sa.String(80),nullable=False,server_default="legacy"))
        batch.add_column(sa.Column("strategy_version",sa.String(40),nullable=False,server_default="legacy"))
        for name in ("constraint_results_json","assumptions_json","unknowns_json","tradeoffs_json"):
            batch.add_column(sa.Column(name,sa.JSON(),nullable=False,server_default=sa.text("'[]'")))
        for name in ("reasoning_json","provenance_json"):
            batch.add_column(sa.Column(name,sa.JSON(),nullable=False,server_default=sa.text("'{}'")))
        batch.add_column(sa.Column("design_engine_version",sa.String(40),nullable=False,server_default="legacy"))
        batch.add_column(sa.Column("design_engine_config_version",sa.String(40),nullable=False,server_default="legacy"))
        batch.add_column(sa.Column("input_world_model_hash",sa.String(64),nullable=False,server_default=""))
        batch.add_column(sa.Column("design_hash",sa.String(64),nullable=True))
        batch.add_column(sa.Column("selected_by",sa.String(36),nullable=True))
        batch.add_column(sa.Column("selected_at",sa.DateTime(timezone=True),nullable=True))
        batch.add_column(sa.Column("selection_reason",sa.Text(),nullable=True))
        batch.add_column(sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")))
        batch.create_index("ix_design_alternatives_design_hash",["design_hash"])
        batch.create_index("ix_design_alternatives_generation_run_id",["generation_run_id"])
        batch.create_index("ix_design_alternatives_status",["status"])
        batch.create_index("ix_design_alternatives_world_model_revision_id",["world_model_revision_id"])
        batch.create_unique_constraint("uq_design_hash_per_version",["project_version_id","design_hash"])
        batch.create_foreign_key("fk_design_alternatives_selected_by","users",["selected_by"],["id"])
        batch.create_foreign_key("fk_design_alternatives_world_revision","world_model_revisions",["world_model_revision_id"],["id"])
        batch.create_foreign_key("fk_design_alternatives_generation_run","design_generation_runs",["generation_run_id"],["id"])
    with op.batch_alter_table("geometry_artifacts") as batch:
        batch.add_column(sa.Column("world_model_revision_id",sa.String(36),nullable=True))
        batch.add_column(sa.Column("input_world_model_hash",sa.String(64),nullable=False,server_default=""))
        batch.add_column(sa.Column("design_hash",sa.String(64),nullable=False,server_default="legacy"))
        batch.add_column(sa.Column("engine_name",sa.String(80),nullable=False,server_default="legacy"))
        batch.add_column(sa.Column("engine_version",sa.String(40),nullable=False,server_default="legacy"))
        batch.add_column(sa.Column("status",sa.String(24),nullable=False,server_default="ARCHIVED"))
        batch.add_column(sa.Column("provenance_json",sa.JSON(),nullable=False,server_default=sa.text("'{}'")))
        batch.add_column(sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")))
        batch.create_index("ix_geometry_artifacts_status",["status"])
        batch.create_index("ix_geometry_artifacts_world_model_revision_id",["world_model_revision_id"])
        batch.create_unique_constraint("uq_geometry_hash_per_version",["project_version_id","geometry_hash"])
        batch.create_foreign_key("fk_geometry_artifacts_world_revision","world_model_revisions",["world_model_revision_id"],["id"])
    bind=op.get_bind()
    bind.execute(sa.text("UPDATE design_alternatives SET status='ARCHIVED' WHERE status NOT IN ('VALID','SELECTED','STALE','INVALID','ARCHIVED','FAILED','GENERATING')"))


def downgrade()->None:
    with op.batch_alter_table("geometry_artifacts") as batch:
        batch.drop_constraint("fk_geometry_artifacts_world_revision",type_="foreignkey")
        batch.drop_constraint("uq_geometry_hash_per_version",type_="unique")
        batch.drop_index("ix_geometry_artifacts_world_model_revision_id");batch.drop_index("ix_geometry_artifacts_status")
        for name in ("updated_at","provenance_json","status","engine_version","engine_name","design_hash","input_world_model_hash","world_model_revision_id"):
            batch.drop_column(name)
    with op.batch_alter_table("design_alternatives") as batch:
        for name in ("fk_design_alternatives_generation_run","fk_design_alternatives_world_revision","fk_design_alternatives_selected_by"):
            batch.drop_constraint(name,type_="foreignkey")
        batch.drop_constraint("uq_design_hash_per_version",type_="unique")
        for name in ("ix_design_alternatives_world_model_revision_id","ix_design_alternatives_status","ix_design_alternatives_generation_run_id","ix_design_alternatives_design_hash"):
            batch.drop_index(name)
        for name in ("updated_at","selection_reason","selected_at","selected_by","provenance_json","design_hash","input_world_model_hash",
                     "design_engine_config_version","design_engine_version","tradeoffs_json","unknowns_json","assumptions_json","reasoning_json",
                     "constraint_results_json","strategy_version","strategy_id","generation_run_id","world_model_revision_id"):
            batch.drop_column(name)
    for column in ("world_model_revision_id","project_version_id","parameter","generation_run_id"):
        op.drop_index(f"ix_design_constraints_{column}",table_name="design_constraints")
    op.drop_table("design_constraints")
    for column in ("world_model_revision_id","world_model_hash","status","project_version_id","project_id","organization_id"):
        op.drop_index(f"ix_design_generation_runs_{column}",table_name="design_generation_runs")
    op.drop_table("design_generation_runs")
