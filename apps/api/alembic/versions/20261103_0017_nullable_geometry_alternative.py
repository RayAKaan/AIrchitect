"""allow geometry artifacts from canonical semantic models

Revision ID: 20261103_0017
Revises: 20261101_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20261103_0017"
down_revision = "20261101_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("geometry_artifacts") as batch_op:
        batch_op.alter_column(
            "alternative_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )


def downgrade() -> None:
    # A downgrade cannot safely restore NOT NULL if canonical-model geometry rows
    # have been written without an alternative. Refuse rather than deleting data.
    bind = op.get_bind()
    missing = bind.execute(
        sa.text("SELECT COUNT(*) FROM geometry_artifacts WHERE alternative_id IS NULL")
    ).scalar_one()
    if missing:
        raise RuntimeError("Cannot downgrade: canonical geometry artifacts have no design alternative")
    with op.batch_alter_table("geometry_artifacts") as batch_op:
        batch_op.alter_column(
            "alternative_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
