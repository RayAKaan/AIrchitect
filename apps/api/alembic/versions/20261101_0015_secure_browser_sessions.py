"""secure browser sessions and refresh-token rotation

Revision ID: 20261101_0015
Revises: 20261101_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20261101_0015"
down_revision = "20261101_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_sessions", sa.Column("refresh_token_hash", sa.String(length=64), nullable=True))
    op.add_column("auth_sessions", sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("auth_sessions", "refresh_expires_at")
    op.drop_column("auth_sessions", "refresh_token_hash")
