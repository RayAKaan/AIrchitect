"""identity email verification and password recovery tokens

Revision ID: 20261101_0016
Revises: 20261101_0015
"""
from alembic import op
import sqlalchemy as sa

revision = "20261101_0016"
down_revision = "20261101_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL")
    op.create_table(
        "identity_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_identity_token_hash"),
    )
    op.create_index("ix_identity_tokens_user_id", "identity_tokens", ["user_id"])
    op.create_index("ix_identity_tokens_purpose", "identity_tokens", ["purpose"])
    op.create_index("ix_identity_tokens_expires_at", "identity_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_identity_tokens_expires_at", table_name="identity_tokens")
    op.drop_index("ix_identity_tokens_purpose", table_name="identity_tokens")
    op.drop_index("ix_identity_tokens_user_id", table_name="identity_tokens")
    op.drop_table("identity_tokens")
    op.drop_column("users", "email_verified_at")
