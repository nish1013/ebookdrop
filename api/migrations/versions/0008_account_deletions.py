"""account deletions: the P6 outbox

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    # No foreign key: the account row is gone when its library removal waits.
    op.create_table(
        "account_deletions",
        sa.Column("reader_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("account_deletions_queued", "account_deletions", ["queued_at"])


def downgrade() -> None:
    op.drop_table("account_deletions")
