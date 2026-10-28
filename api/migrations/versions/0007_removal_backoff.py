"""file removals: an attempt count and a next-try time for the P4 back-off

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade() -> None:
    op.add_column(
        "file_removals",
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column("file_removals", sa.Column("next_try_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE file_removals SET next_try_at = queued_at")
    op.alter_column("file_removals", "next_try_at", nullable=False)
    op.drop_index("file_removals_queued", "file_removals")
    op.create_index("file_removals_next_try", "file_removals", ["next_try_at"])


def downgrade() -> None:
    op.drop_index("file_removals_next_try", "file_removals")
    op.create_index("file_removals_queued", "file_removals", ["queued_at"])
    op.drop_column("file_removals", "next_try_at")
    op.drop_column("file_removals", "attempts")
