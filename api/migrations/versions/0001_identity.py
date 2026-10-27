"""identity: accounts, sessions, failed sign-ins

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "accounts_email_key",
        "accounts",
        [sa.text("lower(trim(email))")],
        unique=True,
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.Text, primary_key=True),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sign_in_failures",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("email_key", sa.Text, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "sign_in_failures_email_key_at", "sign_in_failures", ["email_key", "at"]
    )


def downgrade() -> None:
    op.drop_table("sign_in_failures")
    op.drop_table("sessions")
    op.drop_table("accounts")
